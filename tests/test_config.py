from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from crossword import CrosswordConfig, load_config


class ConfigTests(unittest.TestCase):
    def load_text(self, content):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            return load_config(path)

    def test_project_config_matches_defaults(self):
        path = Path(__file__).resolve().parents[1] / "config.toml"
        self.assertEqual(load_config(path), CrosswordConfig())

    def test_custom_rules_and_partial_defaults(self):
        config = self.load_text(
            'directions = ["down"]\nrequire_all_words = false\n'
            '[grid]\nrows = 12\ncolumns = 25\n'
        )
        self.assertEqual((config.grid.rows, config.grid.columns), (12, 25))
        self.assertEqual(config.directions, ("down",))
        self.assertFalse(config.require_all_words)
        self.assertTrue(config.require_connected)
        self.assertEqual(self.load_text(""), CrosswordConfig())

    def test_invalid_rules_fail_clearly(self):
        for content in (
            '[grid]\nrows = 0', '[grid]\ncolumns = true',
            'directions = []', 'directions = ["left"]',
            'directions = ["down", "down"]', 'directions = "down"',
            'require_all_words = "true"', 'language = "fr"',
            'require_all_word = true', '[grid]\nwidth = 20', 'grid = 20',
        ):
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.load_text(content)


if __name__ == "__main__":
    unittest.main()
