import {dictionaryCandidates, solvePuzzle} from './solver.mjs';

async function requestJSON(url, options) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed: ${response.status}`);
  return result;
}

export function requestPuzzle({count = 15, seed = null, language, signal} = {}) {
  return requestJSON('/api/puzzle', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({count, seed, language}), signal,
  });
}

export function requestDictionary({signal, language} = {}) {
  return requestJSON('/api/dictionary' + (language ? '?language=' + encodeURIComponent(language) : ''), {signal});
}

export function checkAnswers(puzzleId, answers, {signal} = {}) {
  return requestJSON('/api/check', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({puzzle_id: puzzleId, answers}), signal,
  });
}

export async function generateAndSolve({count = 15, seed = null, language, signal, ...options} = {}) {
  const puzzle = await requestPuzzle({count, seed, language, signal});
  if (puzzle.status !== 'success') return {puzzle, result: null};
  const dictionary = await requestDictionary({signal, language: puzzle.language});
  const result = await solvePuzzle(puzzle, dictionaryCandidates(dictionary), {...options, signal});
  return {puzzle, result};
}
