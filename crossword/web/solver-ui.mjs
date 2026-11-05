import {requestPuzzle, requestDictionary, checkAnswers} from './puzzle-client.mjs';
import {dictionaryCandidates, solveSteps, wordCells} from './solver.mjs';

const $ = id => document.getElementById(id);
let puzzle, provider, iterator, answers = {}, domains = {}, activeId;
let running = false, loading = false, finished = false, timer, attempts = 0;
let verification = null, checking = false;
function status(message, error = false) {
  $('status').textContent = message;
  $('status').className = error ? 'error' : '';
}
function controls() {
  $('language').disabled = loading || running || checking;
  $('generate').disabled = loading || running || checking;
  $('solve').disabled = loading || running || checking || !puzzle || finished;
  $('step').disabled = loading || running || checking || !puzzle || finished;
  $('pause').disabled = !running;
  $('reset').disabled = loading || checking || !puzzle;
  $('check').disabled = loading || running || checking || !puzzle;
}
function positions(entry) {
  return Array.from({length: entry.length}, (_, i) =>
    `${entry.row + (entry.direction === 'down' ? i : 0)},${entry.column + (entry.direction === 'across' ? i : 0)}`);
}
function render() {
  const cells = new Map(), starts = new Map(), selected = new Set();
  for (const entry of puzzle.entries) {
    starts.set(`${entry.row},${entry.column}`, entry.number);
    positions(entry).forEach((key, i) => {
      const cell = cells.get(key) || '';
      cells.set(key, (answers[entry.id] ? wordCells(answers[entry.id])[i] : null) || cell);
      if (entry.id === activeId) selected.add(key);
    });
  }
  $('grid').style.gridTemplateColumns = `repeat(${puzzle.grid.columns},minmax(0,1fr))`;
  $('grid').style.maxWidth = `${puzzle.grid.columns * 31}px`;
  const fragment = document.createDocumentFragment();
  for (let row = 0; row < puzzle.grid.rows; row++) {
    for (let column = 0; column < puzzle.grid.columns; column++) {
      const key = `${row},${column}`, cell = document.createElement('div');
      cell.className = 'cell' + (!cells.has(key) ? ' block' : selected.has(key) ? ' active' : '');
      cell.textContent = cells.get(key) || '';
      cell.setAttribute('aria-label', `Row ${row + 1}, column ${column + 1}, ${cells.has(key) ? cells.get(key) || 'blank' : 'unused'}`);
      if (starts.has(key)) {
        const number = document.createElement('small');
        number.textContent = starts.get(key);
        cell.append(number);
      }
      fragment.append(cell);
    }
  }
  $('grid').replaceChildren(fragment);
  $('clues').replaceChildren();
  for (const direction of ['across', 'down']) {
    const column = document.createElement('div'), heading = document.createElement('h3');
    heading.textContent = direction === 'across' ? 'Across →' : 'Down ↓';
    column.append(heading);
    for (const entry of puzzle.entries.filter(entry => entry.direction === direction)) {
      const clue = document.createElement('div');
      clue.className = 'clue' + (activeId === entry.id ? ' active' : '');
      const text = document.createElement('div');
      text.textContent = `${entry.number}. ${entry.clue} (${entry.length})`;
      const detail = document.createElement('div');
      detail.className = 'candidate';
      detail.textContent = answers[entry.id] ? `Trying ${answers[entry.id]}` :
        domains[entry.id] ? `${domains[entry.id].length} candidates: ${domains[entry.id].join(', ') || 'none'}` : 'Not evaluated yet';
      if (verification) detail.textContent += ` · ${verification.entries[entry.id]}`;
      clue.append(text, detail);
      column.append(clue);
    }
    $('clues').append(column);
  }
  $('progress').textContent = `${Object.keys(answers).length} / ${puzzle.entries.length} entries filled · ${attempts} attempts`;
}
function log(message) {
  const item = document.createElement('li');
  item.textContent = message;
  $('log').prepend(item);
  while ($('log').children.length > 80) $('log').lastChild.remove();
}
function pause() {
  running = false;
  clearTimeout(timer);
  controls();
}
function reset() {
  pause();
  iterator?.return();
  iterator = null;
  answers = {}; domains = {}; activeId = null; finished = false; attempts = 0; verification = null;
  $('log').replaceChildren();
  render(); controls(); status('Ready. Solve automatically or advance one step.');
}
function advance() {
  try {
    verification = null;
    // Allow time for manual stepping and pauses; attempt count still bounds search.
    iterator ||= solveSteps(puzzle, provider, {timeoutMs: 3600000});
    const {value: event, done} = iterator.next();
    if (done) { pause(); return; }
    activeId = event.entryId;
    if (event.type === 'candidates') {
      domains[event.entryId] = event.candidates;
      log(`${event.entryId}: ${event.candidates.length} candidates match the clue, length, and crossings.`);
    } else if (event.type === 'try') {
      answers[event.entryId] = event.word;
      attempts = event.attempts;
      log(`Try ${event.word} at ${event.entryId}.`);
    } else if (event.type === 'backtrack') {
      delete answers[event.entryId];
      // Other domains were measured in a branch that may no longer apply.
      domains = {};
      log(`Undo ${event.word} at ${event.entryId}: this branch did not solve the puzzle.`);
    } else if (event.type === 'complete') {
      finished = true;
      answers = event.answers;
      attempts = event.attempts;
      domains = {};
      pause();
      status(event.status === 'solved' ? 'Found a consistent solution. Checking with the server…' :
        event.status === 'search_limit' ? 'Search limit reached. Reset to try again.' :
          'No solution found within the dictionary candidates.', event.status !== 'solved');
      log(`Search finished: ${event.status}.`);
      if (event.status === 'solved') void verify();
    }
    render(); controls();
  } catch (error) {
    pause(); finished = true; controls(); status(error.message, true);
  }
}
async function verify() {
  if (checking || !puzzle) return;
  checking = true; controls();
  try {
    verification = await checkAnswers(puzzle.puzzle_id, {...answers});
    status(verification.complete ? `Verified by server: all ${verification.total} answers are correct.` :
      `Server check: ${verification.correct} of ${verification.total} answers correct. See each clue for details.`);
    log(`Server verified ${verification.correct} / ${verification.total} answers.`);
    render();
  } catch (error) {
    status(`Could not verify answers: ${error.message}`, true);
  } finally { checking = false; controls(); }
}
function tick() {
  if (!running) return;
  advance();
  if (running) timer = setTimeout(tick, Math.min(2000, Math.max(0, Number($('speed').value) || 0)));
}
$('solve').onclick = () => { running = true; status('Solving…'); controls(); tick(); };
$('step').onclick = () => { status('Advancing one search step.'); advance(); };
$('pause').onclick = () => { pause(); status('Paused. Continue with Solve or Step.'); };
$('reset').onclick = reset;
$('check').onclick = verify;
$('generate-form').onsubmit = async event => {
  event.preventDefault();
  if (loading || running || checking) return;
  pause(); loading = true; controls(); status('Generating a complete puzzle…');
  try {
    const next = await requestPuzzle({language: $('language').value, count: Number($('word-count').value), seed: $('seed').value === '' ? null : Number($('seed').value)});
    if (next.status !== 'success') { status(next.message, true); return; }
    const dictionary = await requestDictionary({language: next.language});
    puzzle = next; provider = dictionaryCandidates(dictionary);
    $('dimensions').textContent = `${puzzle.grid.rows} × ${puzzle.grid.columns} · ${puzzle.entries.length} entries · ${puzzle.language==='hy'?'Armenian':'English'}`;
    reset();
  } catch (error) { status(error.message, true); }
  finally { loading = false; controls(); }
};

async function initLanguage() {
  loading = true; controls();
  try {
    let saved;
    try { saved = localStorage.getItem('crossword-language'); } catch {}
    const response = await fetch('/api/config' + (saved ? '?language=' + encodeURIComponent(saved) : ''));
    const config = await response.json();
    if (!response.ok) throw new Error(config.error);
    $('language').value = config.language;
  } catch (error) { status(error.message, true); }
  finally { loading = false; controls(); }
}
$('language').onchange = () => {
  pause(); iterator?.return(); iterator = null;
  puzzle = null; provider = null; answers = {}; domains = {}; activeId = null;
  verification = null; finished = false; attempts = 0;
  for (const id of ['grid', 'clues', 'log']) $(id).replaceChildren();
  $('progress').textContent = '';
  $('dimensions').textContent = 'No puzzle loaded.';
  try { localStorage.setItem('crossword-language', $('language').value); } catch {}
  status('Language changed. Generate a puzzle to begin.'); controls();
};
void initLanguage();
