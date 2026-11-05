from dataclasses import replace
import unittest
from crossword.config import CrosswordConfig, GridConfig
from crossword.grid import Grid


class GridTests(unittest.TestCase):
    def grid(self, **changes):
        return Grid(replace(CrosswordConfig(), **changes))

    def test_crossing_and_atomic_rejection(self):
        grid = self.grid()
        grid.place('cat', 2, 2, 'across')
        grid.place('bar', 1, 3, 'down')
        self.assertEqual(grid.cells[2, 3].directions, {'across', 'down'})
        before = dict(grid.cells)
        with self.assertRaisesRegex(ValueError, 'match'):
            grid.place('DOG', 1, 2, 'down')
        self.assertEqual(grid.cells, before)
        self.assertEqual(len(grid.words), 2)

    def test_boundaries_and_inputs(self):
        for args in [('CAT', -1, 0, 'across'), ('CAT', 19, 19, 'down'), ('CAT', 0, 0, 'left'), ('café', 0, 0, 'across'), ('', 0, 0, 'down'), ('CAT', True, 0, 'down')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.grid().place(*args)
        self.grid(grid=GridConfig(1, 3)).place('CAT', 0, 0, 'across')

    def test_neighbors_overlap_duplicates_and_connection(self):
        for args, message in [(('DOG', 3, 2, 'across'), 'side'), (('DOG', 2, 5, 'across'), 'before'), (('AT', 2, 3, 'across'), 'overlap'), (('CAT', 8, 8, 'down'), 'already'), (('DOG', 8, 8, 'down'), 'cross')]:
            grid = self.grid()
            grid.place('CAT', 2, 2, 'across')
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, message):
                grid.place(*args)

    def test_configurable_touching(self):
        grid = self.grid(require_connected=False, allow_side_touching=True)
        grid.place('CAT', 2, 2, 'across')
        grid.place('DOG', 3, 2, 'across')
        grid = self.grid(require_connected=False, allow_diagonal_touching=False)
        grid.place('CAT', 2, 2, 'across')
        with self.assertRaisesRegex(ValueError, 'Diagonal'):
            grid.place('DOG', 3, 5, 'across')
        grid.place('BAR', 1, 3, 'down')

    def test_completion_and_directions(self):
        grid = self.grid(directions=('down',))
        with self.assertRaises(ValueError):
            grid.place('CAT', 0, 0, 'across')
        grid.place('CAT', 0, 0, 'down')
        grid.validate_complete(['cat'])
        with self.assertRaisesRegex(ValueError, 'Unplaced'):
            grid.validate_complete(['cat', 'dog'])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            grid.validate_complete(['cat', 'CAT'])
        self.grid(require_all_words=False).validate_complete(['CAT'])
