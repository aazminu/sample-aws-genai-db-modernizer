/**
 * #482: the Job summary page kept its own engine colour tables instead of reading
 * the shared palette, and its seven-engine hex table was missing two of the nine
 * catalog engines. `ENGINE_COLORS_HEX[primaryTarget]` was therefore `undefined`
 * for a signal routed to either Aurora engine, so the chip rendered with
 * `color: undefined` and `background: 'undefined18'` -- no colour at all.
 *
 * #1088: the Pattern analysis page likewise kept its own seven-engine `ENGINE_COLORS`
 * badge table, missing `aurora_mysql` and `aurora_postgresql`, so their badges fell
 * back to `'grey'` instead of the catalog's `'green'`.
 *
 * The tables as they stood on main are kept verbatim below, so this file also fails if
 * an engine is dropped from the shared lookups again.
 */
import fs from 'fs';
import path from 'path';
import {
  ENGINE_BADGE_COLORS, ENGINE_HEX, ENGINE_LABELS, ENGINE_PICKER_ORDER,
} from '../engineCatalog.generated';
import {
  ENGINE_STYLES,
  DEFAULT_ENGINE_HEX,
  DEFAULT_ENGINE_BADGE_COLOR,
  engineHex,
  engineBadgeColor,
} from '../engineColors';

const JOB_SUMMARY_HEX_BEFORE = {
  dynamodb: '#3184e8',
  documentdb: '#1d8102',
  elasticache: '#d13212',
  opensearch: '#2ea597',
  neptune: '#7d2105',
  keyspaces: '#8b6ccb',
  aurora: '#ec7211',
};

const PATTERN_ANALYSIS_BADGES_BEFORE = {
  dynamodb: 'blue',
  documentdb: 'green',
  elasticache: 'red',
  opensearch: 'grey',
  neptune: 'red',
  keyspaces: 'blue',
  aurora: 'green',
};

test('every engine label resolves to a colour', () => {
  Object.keys(ENGINE_LABELS).forEach((engine) => {
    expect(engineHex(engine)).toMatch(/^#[0-9a-f]{6}$/i);
    expect(engineHex(engine)).toBe(ENGINE_HEX[engine]);
  });
});

test('the engines the job summary table missed resolve to the live UI colour', () => {
  const missed = Object.keys(ENGINE_LABELS).filter((engine) => !(engine in JOB_SUMMARY_HEX_BEFORE));

  // Exactly the two the private table never carried: both aurora_mysql and
  // aurora_postgresql are catalog engines, so both must resolve.
  expect(missed.sort()).toEqual(['aurora_mysql', 'aurora_postgresql']);
  missed.forEach((engine) => {
    expect(engineHex(engine)).toBe('#9c5700');
  });
});

test('the lookup agrees with the assignment gate palette', () => {
  ENGINE_PICKER_ORDER.forEach((engine) => {
    expect(engineHex(engine)).toBe(ENGINE_STYLES[engine].bg);
  });
});

test('an engine the palette does not know still gets a usable colour', () => {
  expect(engineHex('new_engine_from_a_future_catalog')).toBe(DEFAULT_ENGINE_HEX);
  expect(engineHex(undefined)).toBe(DEFAULT_ENGINE_HEX);
  expect(engineHex(null)).toBe(DEFAULT_ENGINE_HEX);
});

test('every catalog engine resolves to a badge colour for PatternAnalysis', () => {
  Object.keys(ENGINE_LABELS).forEach((engine) => {
    expect(['blue', 'grey', 'green', 'red']).toContain(engineBadgeColor(engine));
    expect(engineBadgeColor(engine)).toBe(ENGINE_BADGE_COLORS[engine]);
  });
});

test('the engines the pattern analysis table missed resolve to their catalog badge colour', () => {
  const missed = Object.keys(ENGINE_LABELS).filter((engine) => !(engine in PATTERN_ANALYSIS_BADGES_BEFORE));

  expect(missed.sort()).toEqual(['aurora_mysql', 'aurora_postgresql']);
  missed.forEach((engine) => {
    expect(engineBadgeColor(engine)).toBe('green');
  });
});

test('the badge lookup agrees with the assignment gate palette', () => {
  ENGINE_PICKER_ORDER.forEach((engine) => {
    expect(engineBadgeColor(engine)).toBe(ENGINE_STYLES[engine].badge);
  });
});

test('an engine the badge palette does not know falls back to grey', () => {
  expect(engineBadgeColor('new_engine_from_a_future_catalog')).toBe(DEFAULT_ENGINE_BADGE_COLOR);
  expect(engineBadgeColor(undefined)).toBe(DEFAULT_ENGINE_BADGE_COLOR);
  expect(engineBadgeColor(null)).toBe(DEFAULT_ENGINE_BADGE_COLOR);
});

test('PatternAnalysis reads engine badge colours from the shared helper instead of a private table', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../../pages/PatternAnalysis.js'),
    'utf8',
  );
  expect(source).not.toMatch(/const\s+ENGINE_COLORS\s*=/);
  expect(source).toMatch(/engineBadgeColor\s*\(\s*engine\s*\)/);
});
