import json
from pathlib import Path
from threading import Thread
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import unittest
from unittest.mock import patch

from crossword.config import CrosswordConfig
from crossword.generator import generate, load_dictionary
from crossword.puzzles import PuzzleStore
from crossword.server import make_handler


class PuzzleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CrosswordConfig()
        cls.result = generate(cls.config, load_dictionary(), 15, 1)

    def test_public_layout_and_private_answers(self):
        store = PuzzleStore()
        public = store.create(self.config, self.result)
        self.assertEqual(set(public), {'status', 'puzzle_id', 'language', 'grid', 'entries'})
        self.assertEqual(public['grid'], {'rows': 20, 'columns': 20})
        private = store.get(public['puzzle_id'])
        self.assertEqual(len(public['entries']), 15)
        for entry in public['entries']:
            self.assertEqual(set(entry), {'id', 'number', 'row', 'column',
                                         'direction', 'length', 'clue'})
            word = next(w for w in self.result['words']
                        if (w['row'], w['column'], w['direction']) ==
                        (entry['row'], entry['column'], entry['direction']))
            self.assertEqual(private['answers'][entry['id']], word['word'])
            self.assertEqual(entry['length'], len(word['word']))
            clue = next(c for c in self.result['clues']
                        if c['word'] == word['word'] and c['direction'] == word['direction'])
            self.assertEqual((entry['number'], entry['clue']),
                             (clue['number'], clue['definition']))
        public['entries'].clear()
        private['answers'].clear()
        self.assertEqual(len(store.get(public['puzzle_id'])['puzzle']['entries']), 15)
        self.assertEqual(len(store.get(public['puzzle_id'])['answers']), 15)

    def test_ids_eviction_and_failures(self):
        store = PuzzleStore(capacity=1)
        first = store.create(self.config, self.result)
        for status in ('search_limit', 'impossible'):
            failed = dict(self.result, status=status, message='Could not generate')
            self.assertEqual(store.create(self.config, failed),
                             {'status': status, 'message': 'Could not generate'})
            self.assertIsNotNone(store.get(first['puzzle_id']))
        second = store.create(self.config, self.result)
        self.assertNotEqual(first['puzzle_id'], second['puzzle_id'])
        self.assertIsNone(store.get(first['puzzle_id']))
        self.assertIsNotNone(store.get(second['puzzle_id']))

    def test_answer_checking(self):
        store = PuzzleStore(capacity=1)
        public = store.create(self.config, self.result)
        puzzle_id = public['puzzle_id']
        answers = store.get(puzzle_id)['answers']
        checked = store.check(puzzle_id, {key: word.lower() for key, word in answers.items()})
        self.assertTrue(checked['complete'])
        self.assertEqual(checked['correct'], 15)
        self.assertEqual(set(checked['entries'].values()), {'correct'})
        first, second = list(answers)[:2]
        wrong = 'Z' * len(answers[first])
        checked = store.check(puzzle_id, {first: wrong, second: ''})
        self.assertFalse(checked['complete'])
        self.assertEqual(checked['entries'][first], 'incorrect')
        self.assertEqual(checked['entries'][second], 'unanswered')
        self.assertNotIn(wrong, json.dumps(checked))
        for submitted in ([], {'unknown': 'CAT'}, {first: None}, {first: '1'}, {first: 'A'}):
            with self.assertRaises(ValueError):
                store.check(puzzle_id, submitted)
        store.create(self.config, self.result)
        with self.assertRaises(LookupError):
            store.check(puzzle_id, {})

    def test_http_contract_and_editor_compatibility(self):
        config_path = Path(__file__).resolve().parents[1] / 'config.toml'
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(config_path))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection(*server.server_address, timeout=10)
        self.addCleanup(connection.close)
        try:
            for path in ('/solver.mjs', '/puzzle-client.mjs', '/solver-ui.mjs', '/solve', '/api/dictionary'):
                connection.request('GET', path)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                body = response.read()
                if path.endswith('.mjs'):
                    self.assertIn('text/javascript', response.getheader('Content-Type'))
                    self.assertTrue(body)
                elif path == '/api/dictionary':
                    self.assertEqual(json.loads(body), load_dictionary())
                else:
                    self.assertIn(b'Check answers', body)

            def post(path, body):
                connection.request('POST', path, json.dumps(body),
                                   {'Content-Type': 'application/json'})
                response = connection.getresponse()
                return response.status, json.loads(response.read())

            status, public = post('/api/puzzle', {'count': 15, 'seed': 1})
            self.assertEqual(status, 200)
            self.assertEqual(public['status'], 'success')
            self.assertEqual(len(public['entries']), 15)
            self.assertNotIn('seed', public)
            self.assertNotIn('selected_words', public)
            puzzle_id = public['puzzle_id']
            status, editor = post('/api/generate', {'count': 15, 'seed': 1})
            self.assertEqual(status, 200)
            self.assertEqual(editor, self.result)
            answers = {f"{clue['number']}-{clue['direction']}": clue['word'] for clue in editor['clues']}
            status, checked = post('/api/check', {'puzzle_id': puzzle_id, 'answers': answers})
            self.assertEqual(status, 200)
            self.assertTrue(checked['complete'])
            self.assertEqual(checked['correct'], 15)
            self.assertNotIn('answers', checked)
            status, partial = post('/api/check', {'puzzle_id': puzzle_id, 'answers': {}})
            self.assertEqual(status, 200)
            self.assertFalse(partial['complete'])
            status, missing = post('/api/check', {'puzzle_id': 'expired', 'answers': {}})
            self.assertEqual(status, 404)
            for body in ({}, {'puzzle_id': puzzle_id, 'answers': []},
                         {'puzzle_id': puzzle_id, 'answers': {'unknown': 'CAT'}}):
                self.assertEqual(post('/api/check', body)[0], 400)
            for body in ([], None, {'count': 0}, {'seed': -1}):
                status, error = post('/api/puzzle', body)
                self.assertEqual(status, 400)
                self.assertIn('error', error)
            with patch('crossword.server.generate', return_value={
                    'status': 'search_limit', 'message': 'Try fewer words',
                    'selected_words': ['SECRET'], 'seed': 1}):
                status, failed = post('/api/puzzle', {})
            self.assertEqual(status, 200)
            self.assertEqual(failed, {'status': 'search_limit', 'message': 'Try fewer words'})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
