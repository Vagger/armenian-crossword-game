from dataclasses import replace
import unittest
from crossword.config import CrosswordConfig, GridConfig
from crossword.generator import generate, load_dictionary
from crossword.grid import Grid


class GeneratorTests(unittest.TestCase):
    def test_dictionary_puzzle_and_reproducibility(self):
        config = CrosswordConfig()
        dictionary = load_dictionary()
        first = generate(config, dictionary, 15, 1)
        self.assertEqual(first['status'], 'success')
        self.assertEqual(first, generate(config, dictionary, 15, 1))
        self.assertNotEqual(first['selected_words'], generate(config, dictionary, 15, 2)['selected_words'])
        grid = Grid(config)
        for word in first['words']:
            grid.place(**word)
        grid.validate_complete(first['selected_words'])
        self.assertEqual(len(grid.words), 15)
        self.assertEqual({w.word for w in grid.words}, set(first['selected_words']))
        for clue in first['clues']:
            self.assertEqual(clue['definition'], dictionary[clue['word']])

    def test_limits_do_not_return_partial_success(self):
        result = generate(CrosswordConfig(), load_dictionary(), 100, 1, max_nodes=1)
        self.assertEqual(result['status'], 'search_limit')
        self.assertEqual(result['words'], [])

    def test_impossible_and_input_validation(self):
        tiny = replace(CrosswordConfig(), grid=GridConfig(1, 1))
        self.assertEqual(generate(tiny, {'CAT': 'A pet'}, 1, 0)['status'], 'impossible')
        disconnected = replace(CrosswordConfig(), grid=GridConfig(3, 3))
        self.assertEqual(generate(disconnected, {'AA': 'A', 'BB': 'B'}, 2, 0)['status'], 'impossible')
        for count in (0, len(load_dictionary()) + 1, True, 1.5):
            with self.assertRaises(ValueError):
                generate(CrosswordConfig(), load_dictionary(), count)
        with self.assertRaises(ValueError):
            generate(CrosswordConfig(), load_dictionary(), 1, -1)

    def test_direction_and_disconnected_configuration(self):
        config = replace(CrosswordConfig(), directions=('down',), require_connected=False)
        result = generate(config, {'CAT': 'A pet', 'DOG': 'Another pet'}, 2, 2)
        self.assertEqual(result['status'], 'success')
        self.assertTrue(all(w['direction'] == 'down' for w in result['words']))
