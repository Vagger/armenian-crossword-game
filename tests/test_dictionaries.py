"""Check the bundled word pools as data, including normalization collisions."""
import json
from pathlib import Path
import unittest

from crossword.generator import DICTIONARY_FILES, load_dictionary
from crossword.grid import normalize_word, word_cells


class DictionaryTests(unittest.TestCase):
    def test_each_language_has_500_distinct_usable_answers_and_clues(self):
        for language, filename in DICTIONARY_FILES.items():
            with self.subTest(language=language):
                path = Path(__file__).resolve().parents[1] / 'data' / filename
                pairs = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=list)
                self.assertEqual(len(pairs), 500)
                self.assertEqual(len({word for word, _ in pairs}), 500)
                normalized = [normalize_word(word, language) for word, _ in pairs]
                self.assertEqual(len(set(normalized)), 500)
                self.assertEqual(len(load_dictionary(language=language)), 500)
                clues = []
                for (word, clue), answer in zip(pairs, normalized):
                    self.assertGreaterEqual(len(word_cells(answer)), 2, word)
                    self.assertLessEqual(len(word_cells(answer)), 20, word)
                    self.assertIsInstance(clue, str)
                    self.assertTrue(clue.strip(), word)
                    clues.append(' '.join(clue.casefold().split()))
                # Definition matching must not assign one clue to several answers.
                self.assertEqual(len(set(clues)), 500)
