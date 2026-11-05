"""Bounded randomized backtracking using the shared grid placement rules."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import random
import secrets
import time

from .config import load_config
from .grid import Grid, normalize_word, word_cells

DATA_DIRECTORY = Path(__file__).resolve().parents[1] / 'data'
DICTIONARY_PATH = DATA_DIRECTORY / 'english.json'
DICTIONARY_FILES = {'en': 'english.json', 'hy': 'armenian.json'}


def load_dictionary(path=None, *, language='en'):
    if language not in DICTIONARY_FILES:
        raise ValueError("Language must be 'en' or 'hy'")
    if path is None:
        path = DATA_DIRECTORY / DICTIONARY_FILES[language]
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not data:
        raise ValueError('Dictionary must be a nonempty word-to-definition object')
    result = {}
    for word, definition in data.items():
        normalized = normalize_word(word, language)
        if normalized in result or not isinstance(definition, str) or not definition.strip():
            raise ValueError('Dictionary words must be unique and have nonempty definitions')
        result[normalized] = definition
    return result


def generate(config, dictionary, count=15, seed=None, *, max_nodes=100000, timeout=5.0):
    if type(count) is not int or not 1 <= count <= len(dictionary):
        raise ValueError(f'Word count must be between 1 and {len(dictionary)}')
    if seed is not None and (type(seed) is not int or not 0 <= seed <= 2**32-1):
        raise ValueError('Seed must be an integer between 0 and 4294967295')
    if max_nodes < 1 or timeout <= 0:
        raise ValueError('Search limits must be positive')
    seed = secrets.randbits(32) if seed is None else seed
    rng = random.Random(seed)
    selected = rng.sample(sorted(dictionary), count)
    grid = Grid(config)
    nodes = 0
    deadline = time.monotonic() + timeout
    exhausted = False

    def limited():
        return nodes >= max_nodes or time.monotonic() >= deadline

    def candidates(word):
        if not grid.words or not config.require_connected:
            options = [(r, c, d) for d in config.directions
                       for r in range(config.grid.rows)
                       for c in range(config.grid.columns)
                       if (c + len(word_cells(word)) <= config.grid.columns if d == 'across'
                           else r + len(word_cells(word)) <= config.grid.rows)]
        else:
            options = set()
            for (r, c), cell in grid.cells.items():
                for i, letter in enumerate(word_cells(word)):
                    if cell.letter != letter:
                        continue
                    for d in config.directions:
                        if d not in cell.directions:
                            options.add((r - (i if d == 'down' else 0),
                                         c - (i if d == 'across' else 0), d))
            options = sorted(options)
        rng.shuffle(options)
        if not grid.words:
            options.sort(key=lambda p: abs(p[0] + (len(word_cells(word))/2 if p[2] == 'down' else 0) - config.grid.rows/2)
                         + abs(p[1] + (len(word_cells(word))/2 if p[2] == 'across' else 0) - config.grid.columns/2))
        return options

    def search(remaining):
        nonlocal nodes, exhausted
        if not remaining:
            return True
        if limited():
            exhausted = True
            return False
        order = list(remaining)
        rng.shuffle(order)
        # Prefer longer words initially; try other words too so bridges can be placed first.
        if not grid.words:
            order.sort(key=lambda w: len(word_cells(w)), reverse=True)
        seen = set()
        for word in order:
            if word in seen:
                continue
            seen.add(word)
            for row, column, direction in candidates(word):
                if limited():
                    exhausted = True
                    return False
                nodes += 1
                cells = grid.cells.copy()
                try:
                    grid.place(word, row, column, direction)
                except ValueError:
                    continue
                next_words = list(remaining)
                next_words.remove(word)
                if search(next_words):
                    return True
                grid.cells = cells
                grid.words.pop()
                if exhausted:
                    return False
        return False

    # A word longer than both allowed dimensions is immediately impossible.
    impossible = [w for w in selected if not any(len(word_cells(w)) <= (config.grid.columns if d == 'across' else config.grid.rows) for d in config.directions)]
    success = not impossible and search(selected)
    if success:
        grid.validate_complete(selected)
    starts = sorted({(w.row, w.column) for w in grid.words})
    numbers = {position: i+1 for i, position in enumerate(starts)}
    return {
        'status': 'success' if success else 'search_limit' if exhausted else 'impossible',
        'seed': seed, 'nodes': nodes, 'selected_words': selected,
        'words': [asdict(w) for w in grid.words] if success else [],
        'clues': [{'number': numbers[w.row, w.column], 'direction': w.direction,
                   'definition': dictionary[w.word], 'word': w.word} for w in grid.words] if success else [],
        'message': f'Placed all {count} selected words.' if success else
                   'Search limit reached. Try another seed, fewer words, or a larger grid.' if exhausted else
                   'No layout exists for these selected words under the configured rules.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config.toml')
    parser.add_argument('--dictionary', help='Override the dictionary selected by config language')
    parser.add_argument('--count', type=int, default=15)
    parser.add_argument('--seed', type=int)
    args = parser.parse_args()
    config = load_config(args.config)
    result = generate(config, load_dictionary(args.dictionary, language=config.language), args.count, args.seed)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result['status'] == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
