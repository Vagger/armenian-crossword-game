"""Grid placement model with zero-based coordinates and atomic validation."""
from collections import Counter
from dataclasses import dataclass
from .config import CrosswordConfig


def normalize_word(word):
    if not isinstance(word, str) or not word or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' for c in word):
        raise ValueError('Use English letters A–Z only, without spaces or punctuation')
    return word.upper()


@dataclass(frozen=True)
class PlacedWord:
    word: str
    row: int
    column: int
    direction: str

    def positions(self):
        return [(self.row + (i if self.direction == 'down' else 0),
                 self.column + (i if self.direction == 'across' else 0)) for i in range(len(self.word))]


@dataclass(frozen=True)
class Cell:
    letter: str
    directions: frozenset[str]


class Grid:
    def __init__(self, config: CrosswordConfig):
        self.config = config
        self.cells = {}
        self.words = []

    def place(self, word, row, column, direction):
        word = normalize_word(word)
        if type(row) is not int or type(column) is not int:
            raise ValueError('Row and column must be integers')
        if direction not in self.config.directions:
            raise ValueError('Direction is not permitted')
        if not self.config.allow_duplicate_words and any(w.word == word for w in self.words):
            raise ValueError('Word already placed')
        placed = PlacedWord(word, row, column, direction)
        positions = placed.positions()
        crossings = set()
        for (r, c), letter in zip(positions, word):
            if not (0 <= r < self.config.grid.rows and 0 <= c < self.config.grid.columns):
                raise ValueError('Word extends beyond the grid boundary')
            cell = self.cells.get((r, c))
            if cell:
                if cell.letter != letter:
                    raise ValueError('Crossing letters must match')
                if direction in cell.directions:
                    raise ValueError('Words cannot overlap in the same direction')
                crossings.add((r, c))
        dr, dc = (0, 1) if direction == 'across' else (1, 0)
        if not self.config.allow_side_touching:
            end_r, end_c = positions[-1]
            if (row-dr, column-dc) in self.cells or (end_r+dr, end_c+dc) in self.cells:
                raise ValueError('Leave an empty cell before and after the word')
            for r, c in set(positions) - crossings:
                if any(p in self.cells for p in ((r+dc, c+dr), (r-dc, c-dr))):
                    raise ValueError('Words cannot touch side by side without a crossing')
        if not self.config.allow_diagonal_touching:
            for r, c in positions:
                for rr, cc in ((r-1,c-1),(r-1,c+1),(r+1,c-1),(r+1,c+1)):
                    if (rr, cc) in self.cells and (r, cc) not in crossings and (rr, c) not in crossings:
                        raise ValueError('Diagonal touching is disabled')
        if self.words and self.config.require_connected and not crossings:
            raise ValueError('Word must cross an existing word')
        for position, letter in zip(positions, word):
            old = self.cells.get(position)
            self.cells[position] = Cell(letter, (old.directions if old else frozenset()) | frozenset([direction]))
        self.words.append(placed)
        return placed

    def validate_complete(self, supplied_words):
        required = Counter(normalize_word(w) for w in supplied_words)
        if not self.config.allow_duplicate_words and any(n > 1 for n in required.values()):
            raise ValueError('Supplied list contains duplicate words')
        missing = required - Counter(w.word for w in self.words)
        if self.config.require_all_words and missing:
            raise ValueError('Unplaced words: ' + ', '.join(missing.elements()))
