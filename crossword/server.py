"""Run the local editor with python3.12 -m crossword.server."""
import argparse
from dataclasses import asdict, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from .config import load_config
from .grid import Grid
from .generator import generate, load_dictionary
from .puzzles import PuzzleStore


def make_handler(config_path):
    puzzles = PuzzleStore()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, value, status=200):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def request_config(self, language=None):
            config = load_config(config_path)
            return replace(config, language=language) if language is not None else config

        def do_GET(self):
            url = urlsplit(self.path)
            language = parse_qs(url.query, keep_blank_values=True).get('language', [None])[0]
            if url.path == '/api/dictionary':
                try:
                    self.reply(load_dictionary(language=self.request_config(language).language))
                except (ValueError, OSError) as error:
                    self.reply({'error': str(error)}, 400)
            elif url.path == '/api/config':
                try:
                    self.reply(asdict(self.request_config(language)))
                except (ValueError, OSError) as error:
                    self.reply({'error': str(error)}, 400)
            elif self.path in ('/', '/solve', '/solver.mjs', '/puzzle-client.mjs', '/solver-ui.mjs'):
                filename = {'/': 'index.html', '/solve': 'solve.html'}.get(self.path, self.path[1:])
                body = Path(__file__).with_name('web').joinpath(filename).read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8' if filename.endswith('.html')
                                 else 'text/javascript; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path not in ('/api/validate', '/api/generate', '/api/puzzle', '/api/check'):
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 100000:
                    raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Request body must be a JSON object')
                if self.path == '/api/check':
                    self.reply(puzzles.check(data['puzzle_id'], data['answers']))
                    return
                if self.path in ('/api/generate', '/api/puzzle'):
                    config = self.request_config(data.get('language'))
                    result = generate(config, load_dictionary(language=config.language),
                                      data.get('count', 15), data.get('seed'))
                    self.reply(puzzles.create(config, result)
                               if self.path == '/api/puzzle' else result)
                    return
                grid = Grid(self.request_config(data.get('language')))
                for word in data['words']:
                    grid.place(**word)
                if data.get('finalize'):
                    grid.validate_complete(data['supplied_words'])
                self.reply({'words': [asdict(w) for w in grid.words]})
            except KeyError as error:
                self.reply({'error': f'Missing request field: {error.args[0]}'}, 400)
            except LookupError as error:
                self.reply({'error': str(error)}, 404)
            except (ValueError, TypeError, OSError) as error:
                self.reply({'error': str(error)}, 400)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.toml')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    load_config(args.config)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(args.config))
    print(f'Crossword editor: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
