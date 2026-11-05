export const wordCells = word => word.toUpperCase().match(/ՈՒ|ԵՒ|./gu) || [];

// Candidate generation is separate from crossing constraints so it can be replaced.
export function dictionaryCandidates(dictionary) {
  const index = new Map();
  const normalize = text => text.trim().replace(/\s+/g, ' ').toLowerCase();
  for (const [word, definition] of Object.entries(dictionary)) {
    const key = normalize(definition);
    if (!index.has(key)) index.set(key, []);
    index.get(key).push(word.toUpperCase());
  }
  return entry => index.get(normalize(entry.clue)) || [];
}

function prepare(puzzle, candidates) {
  if (puzzle.status !== 'success' || !Array.isArray(puzzle.entries) ||
      !puzzle.grid || !Number.isInteger(puzzle.grid.rows) || puzzle.grid.rows < 1 ||
      !Number.isInteger(puzzle.grid.columns) || puzzle.grid.columns < 1) {
    throw new Error('Expected a successful puzzle with grid dimensions and entries');
  }
  const ids = new Set();
  const occupied = new Map();
  return puzzle.entries.map(entry => {
    if (typeof entry.id !== 'string' || !entry.id || ids.has(entry.id) ||
        typeof entry.clue !== 'string' || !Number.isInteger(entry.length) || entry.length < 1 ||
        !Number.isInteger(entry.row) || !Number.isInteger(entry.column) ||
        !['across', 'down'].includes(entry.direction)) {
      throw new Error('Invalid puzzle entry or duplicate entry ID');
    }
    ids.add(entry.id);
    const cells = Array.from({length: entry.length}, (_, i) => {
      const row = entry.row + (entry.direction === 'down' ? i : 0);
      const column = entry.column + (entry.direction === 'across' ? i : 0);
      if (row < 0 || column < 0 || row >= puzzle.grid.rows || column >= puzzle.grid.columns) {
        throw new Error('Entry extends beyond the grid');
      }
      const key = `${row},${column}`;
      const directions = occupied.get(key) || new Set();
      if (directions.has(entry.direction)) throw new Error('Entries overlap in the same direction');
      directions.add(entry.direction);
      occupied.set(key, directions);
      return key;
    });
    const supplied = candidates({...entry});
    if (!Array.isArray(supplied)) throw new Error('Candidate provider must return an array');
    const domain = [...new Set(supplied.filter(word => typeof word === 'string')
      .map(word => word.toUpperCase())
      .filter(word => (puzzle.language === 'hy' ? /^[Ա-Ֆ]+$/ : /^[A-Z]+$/).test(word) && wordCells(word).length === entry.length))];
    return {id: entry.id, cells, domain};
  });
}

// Calling next() performs one observable step. Calling return() stops a run.
// Results mean consistency with the candidate pool, not verification by the server.
export function* solveSteps(puzzle, candidates, {
  maxAttempts = 100000, timeoutMs = 5000, signal, allowDuplicateWords = false,
} = {}) {
  if (!Number.isInteger(maxAttempts) || maxAttempts < 1 ||
      !Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new Error('Invalid search limits');
  const entries = prepare(puzzle, candidates);
  const answers = new Map();
  const started = performance.now();
  let attempts = 0;
  const result = status => ({status, attempts, answers: status === 'solved' ? Object.fromEntries(answers) : {}});
  const stop = () => signal?.aborted ? 'cancelled' :
    performance.now() - started >= timeoutMs ? 'search_limit' : null;

  function* search() {
    const interrupted = stop();
    if (interrupted) return interrupted;
    if (answers.size === entries.length) return 'solved';
    const letters = new Map();
    for (const entry of entries) {
      const word = answers.get(entry.id);
      if (word) entry.cells.forEach((cell, i) => letters.set(cell, wordCells(word)[i]));
    }
    let chosen, options;
    for (const entry of entries) {
      if (answers.has(entry.id)) continue;
      const remaining = entry.domain.filter(word =>
        (allowDuplicateWords || ![...answers.values()].includes(word)) &&
        entry.cells.every((cell, i) => !letters.has(cell) || letters.get(cell) === wordCells(word)[i]));
      yield {type: 'candidates', entryId: entry.id, candidates: [...remaining]};
      if (!remaining.length) return 'unsolved';
      if (!chosen || remaining.length < options.length) {
        chosen = entry;
        options = remaining;
      }
    }
    for (const word of options) {
      const interrupted = stop();
      if (interrupted) return interrupted;
      if (attempts >= maxAttempts) return 'search_limit';
      attempts++;
      answers.set(chosen.id, word);
      yield {type: 'try', entryId: chosen.id, word, attempts};
      const status = yield* search();
      if (status === 'solved') return status;
      answers.delete(chosen.id);
      yield {type: 'backtrack', entryId: chosen.id, word};
      if (status !== 'unsolved') return status;
    }
    return 'unsolved';
  }
  const status = yield* search();
  const final = result(status);
  yield {type: 'complete', ...final};
  return final;
}

// Yield regularly to the browser so rendering and cancellation remain responsive.
export async function solvePuzzle(puzzle, candidates, {onStep, ...options} = {}) {
  const steps = solveSteps(puzzle, candidates, options);
  let count = 0;
  try {
    while (true) {
      const step = steps.next();
      if (step.done) return step.value;
      if (onStep) await onStep(step.value);
      if (++count % 100 === 0) await new Promise(resolve => setTimeout(resolve, 0));
    }
  } finally {
    steps.return();
  }
}
