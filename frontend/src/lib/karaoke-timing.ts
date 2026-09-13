import type { LyricSegment } from './types';

export type TimedWord = NonNullable<LyricSegment['words']>[number];

export function repairTiming(segments: LyricSegment[]): LyricSegment[] {
  const result = segments.map(seg => ({...seg, ...(seg.words ? {words:seg.words.map(w => ({...w}))} : {})}));
  let previous: TimedWord | undefined;
  for (const seg of result) {
    if(seg.locked){previous=undefined;continue;}
    for (const word of seg.words || []) {
      if (![word.start,word.end].every(Number.isFinite) || word.start < 0 || word.end <= word.start) {
        previous = undefined; continue;
      }
      if (previous && previous.end > word.start && previous.end - word.start <= 1 / 16000 && previous.start < word.start) {
        previous.end = word.start;
      }
      previous = word;
    }
  }
  for (const seg of result) {
    if(seg.locked)continue;
    if (seg.words?.length && seg.words.every(w => [w.start,w.end].every(Number.isFinite) && w.start >= 0 && w.end > w.start)) {
      if (Number.isFinite(seg.start)) seg.start = Math.min(seg.start,...seg.words.map(w => w.start));
      if (Number.isFinite(seg.end)) seg.end = Math.max(seg.end,...seg.words.map(w => w.end));
    }
  }
  return result;
}

// Audition the words currently on this row, even when its old envelope was
// left behind by manual edits. Never move or redistribute a word's timing.
export function rowPlaybackRange(segment: LyricSegment): { start: number; end: number } {
  const words = segment.words;
  if (words?.length && words.every(w => Number.isFinite(w.start) && Number.isFinite(w.end) && w.start >= 0 && w.end > w.start)) {
    return {start: Math.min(...words.map(w => w.start)), end: Math.max(...words.map(w => w.end))};
  }
  return {start: segment.start, end: segment.end};
}

export const uppercaseLyric = (text: string): string => text.toLocaleUpperCase('tr-TR');

export function uppercaseLyrics(segments: LyricSegment[]): LyricSegment[] {
  return segments.map(seg => ({...seg, text:uppercaseLyric(seg.text),
    ...(seg.words ? {words:seg.words.map(w => ({...w,word:uppercaseLyric(w.word)}))} : {})}));
}

export function timingIssues(segments: LyricSegment[], includeReview = true, requireWords = true): string[] {
  const issues: string[] = [];
  let previousEnd = 0;
  segments.forEach((seg, i) => {
    const label = `Satır ${i + 1}`;
    if (![seg.start, seg.end].every(Number.isFinite) || seg.start < 0 || seg.end <= seg.start) {
      issues.push(`${label}: geçersiz satır süresi`);
    }
    if (!seg.words?.length) { if(requireWords)issues.push(`${label}: kelimeler sesle hizalanmalı`); return; }
    if (seg.words.map(w => w.word.trim()).join(' ') !== seg.text.trim().split(/\s+/).join(' ')) {
      issues.push(`${label}: metin değişmiş, yeniden hizalama gerekli`);
    }
    seg.words.forEach((w, j) => {
      if (![w.start, w.end].every(Number.isFinite) || w.start < 0 || w.end <= w.start || w.start < previousEnd - 1e-7 || w.start < seg.start - 1e-7 || w.end > seg.end + 1e-7 || (includeReview && w.needs_review) || w.timing_source === 'estimated') {
        issues.push(`${label}, kelime ${j + 1}: zamanlama doğrulanmalı`);
      }
      previousEnd = Math.max(previousEnd, w.end);
    });
  });
  return issues;
}

// Export unaligned lyrics at their measured row interval without inventing word times.
export function videoSegments(segments: LyricSegment[]): LyricSegment[] {
  return segments.map(seg => timingIssues([seg], false).length ? {...seg, words:[]} : seg);
}

export function wordFill(word: TimedWord, time: number, previousEnd = 0, nextStart = Infinity): number {
  // Editor preview follows the stored interval, including uncertain drafts.
  // Confidence remains visible via the ? badge and is checked for export.
  if (![word.start, word.end, time].every(Number.isFinite) || word.start < 0 || word.end <= word.start
    || word.start < previousEnd - 1e-7 || word.end > nextStart + 1e-7 || time < word.start) return 0;
  return Math.min(1, (time - word.start) / (word.end - word.start));
}

export function wordFillWithNeighbors(word: TimedWord, time: number, previous?: TimedWord, next?: TimedWord): number {
  const hasInterval = (neighbor?: TimedWord): neighbor is TimedWord => !!neighbor
    && Number.isFinite(neighbor.start) && Number.isFinite(neighbor.end)
    && neighbor.start >= 0 && neighbor.end > neighbor.start;
  // Unbound words have a zero-length placeholder, not an acoustic boundary.
  return wordFill(word, time, hasInterval(previous) ? previous.end : 0, hasInterval(next) ? next.start : Infinity);
}

// Preserve measured timestamps even when line text/bounds are edited.
// Mismatches are reported by timingIssues, never repaired with invented times.
export function preserveWords(words: TimedWord[] = []): TimedWord[] {
  return words.map(w => ({ ...w }));
}

// Keep unchanged words anchored when text is corrected, inserted or deleted.
// Newly inserted words have no measured duration until they are realigned.
export function reconcileWords(words: TimedWord[], text: string, start = 0): TimedWord[] {
  const tokens = text.trim().split(/\s+/).filter(Boolean);
  const costs = Array.from({length: words.length + 1}, () => Array(tokens.length + 1).fill(0));
  for (let i = 0; i <= words.length; i++) costs[i][0] = i;
  for (let j = 0; j <= tokens.length; j++) costs[0][j] = j;
  for (let i = 1; i <= words.length; i++) for (let j = 1; j <= tokens.length; j++) {
    costs[i][j] = Math.min(costs[i-1][j-1] + (words[i-1].word === tokens[j-1] ? 0 : 1), costs[i-1][j] + 1, costs[i][j-1] + 1);
  }
  const result: TimedWord[] = [];
  let i = words.length, j = tokens.length;
  while (i || j) {
    if (i && j && costs[i][j] === costs[i-1][j-1] + (words[i-1].word === tokens[j-1] ? 0 : 1)) {
      const old = words[--i], word = tokens[--j];
      result.push(old.word === word ? {...old} : {...old, word, needs_review:true});
    } else if (j && costs[i][j] === costs[i][j-1] + 1) {
      const at = words[i-1]?.end ?? start;
      result.push({word:tokens[--j],start:at,end:at,timing_source:'estimated',needs_review:true});
    } else {
      i--;
    }
  }
  return result.reverse();
}

export function serializeProject(segments: LyricSegment[], metadata: Record<string, unknown> = {}): string {
  return JSON.stringify({ ...metadata, version: 2, segments }, null, 2);
}

export function importProject(text: string): LyricSegment[] {
  const parsed = JSON.parse(text);
  const list = Array.isArray(parsed) ? parsed : (parsed.segments || parsed.lyrics || []);
  if (!Array.isArray(list)) throw new Error('Geçersiz proje dosyası');
  return list.map((item: any) => ({
    ...(typeof item.id==='string'?{id:item.id}:{}),
    ...(typeof item.locked==='boolean'?{locked:item.locked}:{}),
    start: Number(item.start), end: Number(item.end), text: String(item.text || item.line || '').trim(),
    words: Array.isArray(item.words) ? item.words.map((w: any) => ({ ...w, word: String(w.word), start: Number(w.start), end: Number(w.end) })) : [],
  })).filter(s => s.text);
}

// Serialize saves across mounts, so closing/reopening cannot reorder writes.
let saveQueue: Promise<unknown> = Promise.resolve();
export function enqueueLyricsSave<T>(save: () => Promise<T>): Promise<T> {
  const next = saveQueue.catch(() => undefined).then(save);
  saveQueue = next;
  return next;
}
