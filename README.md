# Crossword generator

A Python crossword project, starting with configurable puzzle rules.
Requires Python 3.11 or newer. Configuration loading uses the standard library.

## Configuration

Edit `config.toml`, then load the rules from Python:

```python
from crossword import load_config

rules = load_config("config.toml")
print(rules.grid.rows, rules.grid.columns)
```

The initial rules are English, a 20×20 grid, words running right or down,
all supplied words required, and a single connected puzzle. Side touching
and duplicate answers are disabled; diagonal touching is allowed.
Dimensions, direction selection, and the boolean rules are configurable.
Omitted settings use defaults. Unknown settings and invalid values fail
with an error instead of being silently ignored. Paths are relative to the
caller's working directory unless an absolute path is supplied.

The grid model enforces matching letters at crossings, prohibits
overlap in the same direction, and treats English answers as case-insensitive
letters displayed in uppercase. Set `language = "hy"` in `config.toml` to use `data/armenian.json` instead.
Armenian answers are case-insensitive and displayed in uppercase. `ու` (ՈՒ)
and `և` (normalized to ԵՒ) each occupy one cell, including at crossings.
Spaces, punctuation, and letters from other scripts are rejected.

From Python, use `load_dictionary(language="hy")` or
`load_dictionary("path/to/custom.json", language="hy")`. The CLI and server
select the dictionary from the configured language; `--dictionary` overrides
the CLI file path while retaining language validation.

## Automatic generation

Use **Generate crossword** in the editor to select 15 random words by default
from `data/english.json`. Change the count to request up to all 100 words.
Every selected word must fit; the dictionary is a pool, not a requirement to
place all 100 by default. Numbered clues use the dictionary definitions.
The answer key can be expanded below the grid.

The generator uses randomized backtracking and the shared grid model. An
optional integer seed reproduces the selection and search order. Fresh runs
create and display a new seed. Search stops after 100,000 candidate attempts
or five seconds. A time or attempt limit is reported separately from proven
impossibility, with no partial result replacing the current puzzle. A seed
can time out on slower machines even when it succeeds elsewhere.
This initial generator always seeks a complete selection, including when
`require_all_words` is false. Dense 100-word requests may hit the search limit.

You can also generate JSON from the command line:

```sh
/opt/homebrew/bin/python3.12 -m crossword.generator --count 15 --seed 1
```

The JSON includes selected words, placements, definitions, clue numbers,
seed, and status. Unsuccessful searches exit with code 1.

## Local editor

### Solver puzzle endpoint

`POST /api/puzzle` accepts a JSON object with optional `count` (default 15)
and `seed` (default random), using the same limits as generation. For example:

```sh
curl http://127.0.0.1:8000/api/puzzle \
  -H 'Content-Type: application/json' -d '{"count":15}'
```

A successful response contains `status: "success"`, an opaque `puzzle_id`,
`language`, `grid` (`rows` and `columns`), and `entries`. Each entry has a
unique `id` such as `1-across`, a clue `number`, zero-based `row` and `column`,
`direction`, `length`, and `clue`. Entries sharing a start share a number;
their directions distinguish their IDs. Cells covered by entries are playable;
all other cells are unused. No letters, answer list, or generation seed are
included in this response.

Answers stay in server memory for the latest 128 successful puzzles, shared
across requests. IDs expire on eviction or server restart. No public answer
lookup is provided.
Generation failure returns HTTP 200 with only `status` (`search_limit` or
`impossible`) and `message`, and creates no stored puzzle. Invalid requests
return HTTP 400 with `error`.

The existing `/api/generate` endpoint still returns answers for the construction
editor. This separation avoids handing answers to the solver client, but is
not an anti-cheating boundary: a caller with a known seed can reproduce a
puzzle through the editor endpoint.

### Browser solver engine

The browser modules are available at `/solver.mjs` and `/puzzle-client.mjs`.
With the server running, try this in the browser console on the editor page:

```javascript
const {generateAndSolve} = await import('/puzzle-client.mjs');
const attempt = await generateAndSolve({
  count: 15,
  onStep: event => console.log(event),
});
console.log(attempt);
```

The client requests `/api/puzzle` and the full dictionary from
`GET /api/dictionary`. It never requests the editor's completed puzzle.
The dictionary is a general word-to-definition candidate pool, not a list
of the particular puzzle's selected answers. This first candidate provider
matches clues against dictionary definitions, ignoring case and whitespace.
It cannot interpret unfamiliar wording. A replacement synchronous provider
can return multiple possible words per entry without changing the search.

`solveSteps(puzzle, candidates, options)` is a JavaScript generator: each
`next()` emits a `candidates`, `try`, `backtrack`, or `complete` event.
`solvePuzzle` consumes these steps asynchronously and accepts an optional
async `onStep` callback. Search filters candidates by length and crossing
letters, chooses the unfilled entry with the fewest remaining candidates,
and backtracks on contradictions. Duplicate answers are disallowed by default;
set `allowDuplicateWords: true` if needed.

Results contain `status`, `attempts`, and an `answers` object keyed by entry
ID. Status is `solved`, `unsolved` (no solution within the candidate pool),
`search_limit`, or `cancelled`. Only `solved` returns answers. Search defaults
to 100,000 attempts and 5,000 milliseconds, configurable with `maxAttempts`
and `timeoutMs`; an AbortController's `signal` supports cancellation.
`generateAndSolve` returns `{puzzle, result}`; unsuccessful generation returns
`result: null`. A solved result is the first consistent assignment, not a
uniqueness claim or server verification.

Open `/solve` for the solver interface, or follow **Automatic solver** from
the editor. Generate a puzzle, then use **Solve**, **Step**, **Pause**, or
**Reset**. The board highlights the entry being evaluated, clue rows show
candidate counts, and recent activity explains trials and backtracking.
Reset clears the attempt while keeping the puzzle. Failed generation keeps
the previous puzzle. Adjust the delay to watch the search or run it quickly.
The visual session allows an hour of wall time for stepping and pauses,
with the same 100,000-attempt limit.

### Server answer checking

`POST /api/check` accepts `{"puzzle_id":"…","answers":{"1-across":"CAT"}}`.
Answers use entry IDs and case-insensitive letters in the stored puzzle’s language. Missing entries
and empty strings count as unanswered. Unknown entry IDs, invalid characters,
and wrong answer lengths return HTTP 400; expired or unknown puzzles return
HTTP 404. The response contains `puzzle_id`, `complete`, `correct`, `total`,
and `entries` mapping every entry ID to `correct`, `incorrect`, or `unanswered`.
It never returns the expected answers. Checking uses the original stored puzzle,
even if the server's configuration subsequently changes.

The solver automatically checks completed solutions. **Check answers** also
checks a paused or partially filled attempt. Clue rows show the server's
feedback. Reset clears this feedback and the attempt; an expired puzzle requires
generating a new one. `checkAnswers(puzzleId, answers)` in `puzzle-client.mjs`
exposes the same check for other clients.

Run solver checks using Node.js (with a Python 3.11+ executable available):

```sh
CROSSWORD_PYTHON=/opt/homebrew/bin/python3.12 node --test tests/test_solver.mjs
```

### Running the editor

From the project directory, run:

```sh
/opt/homebrew/bin/python3.12 -m crossword.server
```

Open http://127.0.0.1:8000. Click a starting cell, enter a word in the configured language,
and choose across or down. Undo removes the last word; clear resets the grid.
Use the required-word list and Check completion to verify all supplied words
are placed. Drafts are kept in browser memory and cleared on refresh.
Edit `config.toml` and refresh to reload dimensions and rules.
The UI uses 1-based coordinates; the Python model uses 0-based coordinates.
With diagonal touching disabled, the diagonal arms of a legal crossing remain
allowed. The server listens on localhost only and uses the same Python model
as the tests, rather than a separate browser implementation of the rules.

## Checks

```sh
python3.12 -m unittest discover -s tests -v
```

Use a Python 3.11+ executable. On this machine, Python 3.12 is available at
`/opt/homebrew/bin/python3.12`; the system `python3` is Python 3.9.
