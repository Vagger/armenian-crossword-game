"""Public puzzle descriptions and bounded, process-local answer storage."""
from collections import OrderedDict
from copy import deepcopy
import secrets
from threading import Lock
from .grid import normalize_word


class PuzzleStore:
    """Retain the latest puzzles until eviction or server restart."""

    def __init__(self, capacity=128):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('Puzzle capacity must be a positive integer')
        self.capacity = capacity
        self._puzzles = OrderedDict()
        self._lock = Lock()

    def create(self, config, result):
        if result['status'] != 'success':
            return {'status': result['status'], 'message': result['message']}
        clues = {(c['word'], c['direction']): c for c in result['clues']}
        entries = []
        answers = {}
        for word in result['words']:
            clue = clues[word['word'], word['direction']]
            entry_id = f"{clue['number']}-{word['direction']}"
            entries.append({
                'id': entry_id, 'number': clue['number'],
                'row': word['row'], 'column': word['column'],
                'direction': word['direction'], 'length': len(word['word']),
                'clue': clue['definition'],
            })
            answers[entry_id] = word['word']
        entries.sort(key=lambda entry: (entry['number'], entry['direction']))
        with self._lock:
            puzzle_id = secrets.token_urlsafe(24)
            while puzzle_id in self._puzzles:
                puzzle_id = secrets.token_urlsafe(24)
            public = {
                'status': 'success', 'puzzle_id': puzzle_id,
                'language': config.language,
                'grid': {'rows': config.grid.rows, 'columns': config.grid.columns},
                'entries': entries,
            }
            self._puzzles[puzzle_id] = {'puzzle': deepcopy(public), 'answers': answers}
            if len(self._puzzles) > self.capacity:
                self._puzzles.popitem(last=False)
        return public

    def get(self, puzzle_id):
        """Internal lookup for subsequent answer checking; never sent to clients."""
        with self._lock:
            return deepcopy(self._puzzles.get(puzzle_id))

    def check(self, puzzle_id, answers):
        if not isinstance(puzzle_id, str) or not puzzle_id:
            raise ValueError('puzzle_id must be a nonempty string')
        if not isinstance(answers, dict):
            raise ValueError('answers must be an object keyed by entry ID')
        stored = self.get(puzzle_id)
        if stored is None:
            raise LookupError('Puzzle not found or expired. Generate a new puzzle.')
        expected = stored['answers']
        if answers.keys() - expected.keys():
            raise ValueError('Unknown entry ID in answers')
        normalized = {}
        for entry_id, answer in answers.items():
            if answer == '':
                continue
            normalized[entry_id] = normalize_word(answer)
            if len(normalized[entry_id]) != len(expected[entry_id]):
                raise ValueError(f'Answer length does not match entry {entry_id}')
        entries = {entry_id: 'unanswered' if entry_id not in normalized else
                   'correct' if normalized[entry_id] == answer else 'incorrect'
                   for entry_id, answer in expected.items()}
        correct = sum(value == 'correct' for value in entries.values())
        return {'puzzle_id': puzzle_id, 'complete': correct == len(expected),
                'correct': correct, 'total': len(expected), 'entries': entries}
