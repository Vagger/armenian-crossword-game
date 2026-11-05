"""Language selection is per request and never changes the server default."""
from io import BytesIO
import json
from pathlib import Path
import unittest

from crossword.config import load_config
from crossword.generator import load_dictionary
from crossword.server import make_handler


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).resolve().parents[1] / 'config.toml'
        self.handler = object.__new__(make_handler(self.path))
        self.responses = []
        self.handler.reply = lambda value, status=200: self.responses.append((value, status))

    def post(self, path, data):
        body = json.dumps(data).encode()
        self.handler.path = path
        self.handler.headers = {'Content-Length': str(len(body))}
        self.handler.rfile = BytesIO(body)
        self.handler.do_POST()
        return self.responses[-1]

    def test_config_and_dictionary_selection(self):
        default = load_config(self.path)
        for language in ('en', 'hy'):
            self.handler.path = '/api/config?language=' + language
            self.handler.do_GET()
            config, status = self.responses[-1]
            self.assertEqual(status, 200)
            self.assertEqual(config['language'], language)
            self.handler.path = '/api/dictionary?language=' + language
            self.handler.do_GET()
            self.assertEqual(self.responses[-1], (load_dictionary(language=language), 200))
        self.assertEqual(self.handler.request_config(), default)
        self.handler.path = '/api/config?language=fr'
        self.handler.do_GET()
        self.assertEqual(self.responses[-1][1], 400)

    def test_generation_validation_and_checking(self):
        for language in ('en', 'hy'):
            result, status = self.post('/api/puzzle', {'language': language, 'count': 1, 'seed': 1})
            self.assertEqual(status, 200)
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['language'], language)
            checked, status = self.post('/api/check', {'puzzle_id': result['puzzle_id'], 'answers': {}})
            self.assertEqual(status, 200)
            self.assertEqual(checked['total'], 1)
            word = 'CAT' if language == 'en' else 'ԱՐԵՒ'
            result, status = self.post('/api/validate', {'language': language, 'words': [
                {'word': word, 'row': 0, 'column': 0, 'direction': 'across'}]})
            self.assertEqual(status, 200)
            self.assertEqual(result['words'][0]['word'], word)
        self.assertEqual(self.post('/api/puzzle', {'language': 'fr'})[1], 400)
