// FormatDate / formatDateTime live in src/dates.ts so they can be unit-tested
// Without loading the native NAPI addon (which fails outside a built env).
import { formatDate, formatDateTime } from '../src/dates';

class DuckDateTime {
  constructor(private readonly dt: Date) {}
  toJSDate(): Date {
    return this.dt;
  }
}

describe('formatDate (#317)', () => {
  it('accepts ISO date string', () => {
    expect(formatDate('2023-01-17')).toBe('20230117');
  });

  it('accepts Bloomberg-native string unchanged', () => {
    expect(formatDate('20230117')).toBe('20230117');
  });

  it('accepts a Date object', () => {
    expect(formatDate(new Date(Date.UTC(2023, 0, 17)))).toBe('20230117');
  });

  it('accepts epoch milliseconds', () => {
    expect(formatDate(Date.UTC(2023, 0, 17))).toBe('20230117');
  });

  it('accepts duck-typed Luxon DateTime', () => {
    const dt = new DuckDateTime(new Date(Date.UTC(2023, 0, 17)));
    expect(formatDate(dt)).toBe('20230117');
  });

  it('returns undefined for null/undefined/empty', () => {
    expect(formatDate(undefined)).toBeUndefined();
    expect(formatDate(null)).toBeUndefined();
    expect(formatDate('')).toBeUndefined();
  });

  it('rejects ambiguous formats', () => {
    expect(() => formatDate('01/17/2023')).toThrow(/Ambiguous/);
    expect(() => formatDate('1/17/23')).toThrow(/Ambiguous/);
    expect(() => formatDate('17-01-2023')).toThrow(/Ambiguous/);
  });
});

describe('formatDateTime (#317)', () => {
  it('preserves naive ISO strings (request_tz handles them)', () => {
    expect(formatDateTime('2023-01-17T10:30:00')).toBe('2023-01-17T10:30:00');
  });

  it('preserves tz-aware ISO strings', () => {
    expect(formatDateTime('2023-01-17T10:30:00-05:00')).toBe('2023-01-17T10:30:00-05:00');
  });

  it('expands Bloomberg-native to ISO midnight', () => {
    expect(formatDateTime('20230117')).toBe('2023-01-17T00:00:00');
  });

  it('converts a Date to ISO with offset', () => {
    const dt = new Date(Date.UTC(2023, 0, 17, 10, 30));
    const formatted = formatDateTime(dt);
    expect(formatted).toBe('2023-01-17T10:30:00.000Z');
  });

  it('converts a duck-typed Luxon DateTime', () => {
    const dt = new DuckDateTime(new Date(Date.UTC(2023, 0, 17, 10, 30)));
    expect(formatDateTime(dt)).toBe('2023-01-17T10:30:00.000Z');
  });

  it('returns undefined for null/undefined/empty', () => {
    expect(formatDateTime(undefined)).toBeUndefined();
    expect(formatDateTime(null)).toBeUndefined();
    expect(formatDateTime('')).toBeUndefined();
  });

  it('rejects ambiguous datetime formats', () => {
    expect(() => formatDateTime('01/17/2023 10:30:00')).toThrow(/Ambiguous/);
    expect(() => formatDateTime('01/17/2023T10:30:00')).toThrow(/Ambiguous/);
  });
});
