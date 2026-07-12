import { test } from 'node:test';
import assert from 'node:assert/strict';
import { roleFuzzyMatch } from './role-matcher.mjs';

// --- True positives: near-duplicate wording of the same role ---

test('matches identical titles', () => {
  assert.equal(roleFuzzyMatch('Backend Engineer', 'Backend Engineer'), true);
});

test('matches title with a seniority/version suffix appended', () => {
  assert.equal(roleFuzzyMatch('Backend Engineer', 'Backend Engineer II'), true);
});

test('matches title with a parenthetical location/work-mode tag', () => {
  assert.equal(roleFuzzyMatch('Backend Engineer', 'Backend Engineer (Remote)'), true);
});

test('matches title with a parenthetical hybrid tag on both sides', () => {
  assert.equal(roleFuzzyMatch('Backend Engineer (Hybrid)', 'Backend Engineer (Remote)'), true);
});

test('matches titles differing only in case and punctuation', () => {
  assert.equal(roleFuzzyMatch('backend engineer', 'Backend Engineer!'), true);
});

test('matches titles differing only in whitespace', () => {
  assert.equal(roleFuzzyMatch('Backend  Engineer', 'Backend Engineer'), true);
});

test('matches "Senior Backend Engineer" vs "Backend Engineer, Senior"', () => {
  assert.equal(roleFuzzyMatch('Senior Backend Engineer', 'Backend Engineer, Senior'), true);
});

// --- True negatives: clearly distinct roles ---

test('does not match Software Engineer vs Product Manager', () => {
  assert.equal(roleFuzzyMatch('Software Engineer', 'Product Manager'), false);
});

test('does not match Data Scientist vs Data Analyst', () => {
  assert.equal(roleFuzzyMatch('Data Scientist', 'Data Analyst'), false);
});

test('does not match Software Engineer vs Software Architect', () => {
  assert.equal(roleFuzzyMatch('Software Engineer', 'Software Architect'), false);
});

test('does not match Frontend Engineer vs Backend Engineer', () => {
  assert.equal(roleFuzzyMatch('Frontend Engineer', 'Backend Engineer'), false);
});

test('does not match unrelated single-word titles', () => {
  assert.equal(roleFuzzyMatch('Recruiter', 'Engineer'), false);
});

// --- Edge cases ---

test('empty vs non-empty title does not match', () => {
  assert.equal(roleFuzzyMatch('', 'Backend Engineer'), false);
});

test('two empty titles match (nothing to disagree on)', () => {
  assert.equal(roleFuzzyMatch('', ''), true);
});

test('handles null/undefined input without throwing', () => {
  assert.equal(roleFuzzyMatch(null, undefined), true);
  assert.equal(roleFuzzyMatch(null, 'Backend Engineer'), false);
});
