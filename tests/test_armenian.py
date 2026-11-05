import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from crossword.config import CrosswordConfig, GridConfig, load_config
from crossword.generator import generate, load_dictionary
from crossword.grid import Grid, normalize_word, word_cells
from crossword.puzzles import PuzzleStore


class ArmenianTests(unittest.TestCase):
    def test_normalization_and_single_cell_letters(self):
        self.assertEqual(normalize_word('արև', 'hy'), 'ԱՐԵՒ')
        self.assertEqual(word_cells(normalize_word('ուսուցիչ', 'hy')),
                         ['ՈՒ', 'Ս', 'ՈՒ', 'Ց', 'Ի', 'Չ'])
        self.assertEqual(word_cells(normalize_word('արև', 'hy')), ['Ա', 'Ր', 'ԵՒ'])
        for word in ('CAT', 'Աa', 'արև։', 'երկու բառ', ''):
            with self.subTest(word=word), self.assertRaises(ValueError):
                normalize_word(word, 'hy')
        with self.assertRaises(ValueError):
            normalize_word('արև')

    def test_crossings_boundaries_and_completion(self):
        grid = Grid(CrosswordConfig(language='hy', grid=GridConfig(4, 3)))
        grid.place('արև', 3, 0, 'across')
        grid.place('տերև', 0, 2, 'down')
        self.assertEqual(grid.cells[3, 2].letter, 'ԵՒ')
        grid.validate_complete(['արև', 'տերև'])
        grid = Grid(CrosswordConfig(language='hy', grid=GridConfig(3, 3)))
        grid.place('տուն', 1, 0, 'across')
        grid.place('շուն', 0, 1, 'down')
        self.assertEqual(grid.cells[1, 1].letter, 'ՈՒ')
        self.assertEqual(len(grid.cells), 5)

    def test_dictionary_config_generation_and_checking(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text('language = "hy"', encoding='utf-8')
            config = load_config(path)
            dictionary = load_dictionary(language=config.language)
            self.assertEqual(len(dictionary), 500)
            custom = Path(directory) / 'words.json'
            custom.write_text(json.dumps({'արև': 'Լույս տվող աստղ։', 'ԱՐԵՒ': 'Կրկնություն։'}))
            with self.assertRaises(ValueError):
                load_dictionary(custom, language='hy')
        result = generate(config, dictionary, 15, 1)
        self.assertEqual(result['status'], 'success')
        grid = Grid(config)
        for word in result['words']:
            grid.place(**word)
        grid.validate_complete(result['selected_words'])
        store = PuzzleStore()
        public = store.create(config, result)
        answers = store.get(public['puzzle_id'])['answers']
        for entry in public['entries']:
            self.assertEqual(entry['length'], len(word_cells(answers[entry['id']])))
        self.assertTrue(store.check(public['puzzle_id'],
                                   {k: v.lower() for k, v in answers.items()})['complete'])
