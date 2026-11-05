import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {dictionaryCandidates, solveSteps, solvePuzzle} from '../crossword/web/solver.mjs';
import {generateAndSolve, checkAnswers} from '../crossword/web/puzzle-client.mjs';

const puzzle = {
  status: 'success', grid: {rows: 2, columns: 2}, entries: [
    {id: '1-across', row: 0, column: 0, direction: 'across', length: 2, clue: 'First'},
    {id: '2-down', row: 0, column: 1, direction: 'down', length: 2, clue: 'Second'},
  ],
};
const candidates = entry => entry.id === '1-across' ? ['AB', 'CD'] : ['DX', 'DY'];

test('crossings reject a wrong branch and backtracking finds a consistent solution', async () => {
  const events = [];
  const original = structuredClone(puzzle);
  const result = await solvePuzzle(puzzle, candidates, {onStep: step => events.push(step)});
  assert.equal(result.status, 'solved');
  assert.deepEqual(result.answers, {'1-across': 'CD', '2-down': 'DX'});
  assert.ok(events.some(event => event.type === 'backtrack' && event.word === 'AB'));
  assert.ok(events.some(event => event.type === 'candidates' && !event.candidates.length));
  assert.deepEqual(puzzle, original);
});

test('unknown clues and inconsistent candidates return unsolved without partial answers', async () => {
  for (const provider of [() => [], entry => entry.id === '1-across' ? ['AB'] : ['DX']]) {
    const result = await solvePuzzle(puzzle, provider);
    assert.equal(result.status, 'unsolved');
    assert.deepEqual(result.answers, {});
  }
});

test('chooses the smallest remaining domain and can permit duplicate answers', async () => {
  const events = [];
  await solvePuzzle(puzzle, entry => entry.id === '1-across' ? ['AB', 'CD'] : ['BX'],
    {onStep: event => events.push(event)});
  assert.equal(events.find(event => event.type === 'try').entryId, '2-down');
  const provider = () => ['AA'];
  assert.equal((await solvePuzzle(puzzle, provider)).status, 'unsolved');
  assert.equal((await solvePuzzle(puzzle, provider, {allowDuplicateWords: true})).status, 'solved');
});

test('step iteration, cancellation and limits produce distinct outcomes', async () => {
  const steps = solveSteps(puzzle, candidates);
  assert.equal(steps.next().value.type, 'candidates');
  assert.equal(steps.return().done, true);
  const limited = await solvePuzzle(puzzle, candidates, {maxAttempts: 1});
  assert.equal(limited.status, 'search_limit');
  assert.deepEqual(limited.answers, {});
  const timed = solveSteps(puzzle, candidates, {timeoutMs: 1});
  timed.next();
  await new Promise(resolve => setTimeout(resolve, 10));
  let step;
  do { step = timed.next(); } while (!step.done);
  assert.equal(step.value.status, 'search_limit');
  const controller = new AbortController();
  const cancelled = await solvePuzzle(puzzle, candidates, {
    signal: controller.signal,
    onStep: event => { if (event.type === 'try') controller.abort(); },
  });
  assert.equal(cancelled.status, 'cancelled');
  assert.deepEqual(cancelled.answers, {});
});

test('dictionary lookup normalizes clues and filters candidate lengths and letters', async () => {
  const provider = dictionaryCandidates({ab: ' FIRST ', CD: 'Second', WRONG: 'First'});
  assert.deepEqual(provider({clue: 'first'}), ['AB', 'WRONG']);
  const result = await solvePuzzle(puzzle, provider);
  assert.equal(result.status, 'unsolved');
  assert.throws(() => solveSteps({...puzzle, entries: [puzzle.entries[0], puzzle.entries[0]]}, candidates).next(),
    /duplicate/);
  assert.throws(() => solveSteps(puzzle, candidates, {maxAttempts: 0}).next(), /limits/);
});

test('solves actual generated public puzzles using the full dictionary', async () => {
  const root = new URL('../', import.meta.url);
  const generated = JSON.parse(execFileSync(process.env.CROSSWORD_PYTHON || 'python3.12', ['-c', `
import json
from crossword.config import CrosswordConfig
from crossword.generator import generate, load_dictionary
from crossword.puzzles import PuzzleStore
config = CrosswordConfig()
store = PuzzleStore()
items = []
for count, seed in ((15, 1), (1, 2), (1, 3), (1, 4), (5, 5)):
    public = store.create(config, generate(config, load_dictionary(), count, seed))
    assert public['status'] == 'success', public
    items.append({'puzzle': public, 'answers': store.get(public['puzzle_id'])['answers']})
print(json.dumps(items))
`], {cwd: root, encoding: 'utf8'}));
  const dictionary = JSON.parse(readFileSync(new URL('../data/english.json', import.meta.url)));
  for (const item of generated) {
    const result = await solvePuzzle(item.puzzle, dictionaryCandidates(dictionary));
    assert.equal(result.status, 'solved');
    assert.deepEqual(result.answers, item.answers);
  }
});

test('client requests a public puzzle and dictionary and reports generation failure', async () => {
  const savedFetch = globalThis.fetch;
  const requests = [];
  try {
    globalThis.fetch = async (url, options) => {
      requests.push({url, options});
      return {ok: true, json: async () => url === '/api/puzzle' ? puzzle : {AB: 'First', BX: 'Second'}};
    };
    const completed = await generateAndSolve({count: 2});
    assert.equal(completed.result.status, 'solved');
    assert.deepEqual(requests.map(request => request.url), ['/api/puzzle', '/api/dictionary']);
    assert.deepEqual(JSON.parse(requests[0].options.body), {count: 2, seed: null});
    await checkAnswers('example-id', {'1-across': 'AB'});
    assert.equal(requests[2].url, '/api/check');
    assert.deepEqual(JSON.parse(requests[2].options.body),
      {puzzle_id: 'example-id', answers: {'1-across': 'AB'}});
    globalThis.fetch = async () => ({ok: true, json: async () => ({status: 'search_limit'})});
    assert.equal((await generateAndSolve()).result, null);
    globalThis.fetch = async () => ({ok: false, json: async () => ({error: 'Invalid count'})});
    await assert.rejects(generateAndSolve(), /Invalid count/);
  } finally {
    globalThis.fetch = savedFetch;
  }
});
