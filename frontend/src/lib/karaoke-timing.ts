import type { LyricSegment } from './types';

export type TimedWord = NonNullable<LyricSegment['words']>[number];

const syllableTextKey=(text:string)=>text.normalize('NFC').replaceAll('İ','i').replaceAll('I','ı').toLowerCase().replace(/[^\p{L}\p{M}\p{N}]/gu,'');
export function syllablePieces(word:TimedWord):Array<{text:string;start:number;end:number;score:number}> {
  const punctuationParts=Boolean(word.timing_parts?.length);
  const parts=punctuationParts?word.timing_parts:word.syllables;
  if(!Array.isArray(parts)||!parts.length||word.needs_review||['estimated','repeat_inferred'].includes(word.timing_source||''))return [];
  if(parts.some(p=>!p||typeof p.text!=='string')||syllableTextKey(parts.map(p=>p.text).join(''))!==syllableTextKey(word.word))return [];
  const ref=punctuationParts?word.timing_parts_reference:word.syllable_reference;
  if(punctuationParts&&!ref)return [];
  if(ref){if(typeof ref.word_text!=='string'||ref.word_start!==word.start||ref.word_end!==word.end||syllableTextKey(ref.word_text)!==syllableTextKey(word.word))return [];}
  else if(Math.abs(parts[0].start-word.start)>.02||Math.abs(parts.at(-1)!.end-word.end)>.02)return [];
  const raw=Array.from(word.word.normalize('NFC'));let cursor=0,previous=word.start;
  const result=[];
  for(let i=0;i<parts.length;i++){
    const p=parts[i];
    if(![p.start,p.end,p.score].every(Number.isFinite)||p.score<(punctuationParts ? .5 : .55)||p.needs_review||p.start<previous||p.end<=p.start||p.start<word.start||p.end>word.end)return [];
    let count=Array.from(syllableTextKey(p.text)).length;const first=cursor;
    while(cursor<raw.length&&count){if(/[\p{L}\p{M}\p{N}]/u.test(raw[cursor]))count--;cursor++;}
    if(count)return [];
    if(i===parts.length-1)cursor=raw.length;
    result.push({text:raw.slice(first,cursor).join(''),start:p.start,end:p.end,score:p.score});previous=p.end;
  }
  return result;
}

export function syllableFill(word:TimedWord,time:number):number|null {
  const parts=syllablePieces(word);
  if(!parts.length)return null;
  const total=parts.reduce((sum,p)=>sum+Array.from(p.text).length,0);
  return parts.reduce((sum,p)=>sum+Array.from(p.text).length*Math.max(0,Math.min(1,(time-p.start)/(p.end-p.start))),0)/total;
}

export function preferLyricDraft(draft:{segments:LyricSegment[];modifiedAt?:number;baseRevision?:string}|null,saved:{segments:LyricSegment[];updated_at?:string;revision?:string}|null):boolean {
  if(!draft||!Array.isArray(draft.segments))return false;
  if(!saved)return true;
  if(saved.revision!==undefined)return draft.baseRevision===saved.revision;
  if(!draft.modifiedAt)return false; // Legacy drafts cannot supersede a persisted project.
  const value=saved.updated_at;
  const savedAt=value?Date.parse(/[zZ]|[+-]\d\d:\d\d$/.test(value)?value:value+'Z'):0;
  return draft.modifiedAt>=(Number.isFinite(savedAt)?savedAt:0);
}

// An instrumental label deliberately fills its whole display interval.
export function instrumentalTiming(segment:LyricSegment):LyricSegment {
  if(!/^\s*solo[.\s…!]*$/i.test(segment.text)||![segment.start,segment.end].every(Number.isFinite)||segment.start<0||segment.end<=segment.start)return segment;
  return {...segment,words:[{word:segment.text.trim(),start:segment.start,end:segment.end,timing_source:'manual',needs_review:false}]};
}

export function applyEditedWordTimes(segment:LyricSegment,words:TimedWord[]):LyricSegment {
  if(!words.length)return {...segment,words};
  const solo=instrumentalTiming(segment)!==segment;
  return {...segment,words,start:solo?words[0].start:Math.min(segment.start,words[0].start),
    end:solo?words[words.length-1].end:Math.max(segment.end,words[words.length-1].end)};
}

export function repairTiming(segments: LyricSegment[]): LyricSegment[] {
  const result = segments.map(original => {const seg=original.locked?original:instrumentalTiming(original);return {...seg, ...(seg.words ? {words:seg.words.map(w => ({...w}))} : {})};});
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
    seg=instrumentalTiming(seg);
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

// Match the renderer: an explicitly unbound word stays white while measured
// neighbours keep their sweep. Invalid measured times must still block export.
export function renderTimingIssues(segments: LyricSegment[]): string[] {
  const checked: LyricSegment[] = [];
  for (const [i, segment] of segments.entries()) {
    const words = segment.words || [];
    const label = `Satır ${i + 1}`;
    if (words.length && words.map(w => w.word.trim()).join(' ') !== segment.text.trim().split(/\s+/).join(' ')) {
      return [`${label}: metin değişmiş, yeniden hizalama gerekli`];
    }
    for (const [j, word] of words.entries()) {
      const placeholder = word.end === word.start && word.timing_source === 'estimated' && word.needs_review;
      if (![word.start, word.end].every(Number.isFinite) || word.start < 0 || word.end < word.start || (word.end === word.start && !placeholder)) {
        return [`${label}, kelime ${j + 1}: geçersiz kelime süresi`];
      }
    }
    const timed = words.filter(w => w.end > w.start);
    checked.push({...segment, words:timed, text:timed.length ? timed.map(w => w.word.trim()).join(' ') : segment.text});
  }
  return timingIssues(checked, false, false).map(issue => issue.replace(/^Satır (\d+), kelime (\d+):/, (_, row, word) => {
    const indices = (segments[Number(row)-1].words || []).flatMap((w, i) => w.end > w.start ? [i+1] : []);
    return `Satır ${row}, kelime ${indices[Number(word)-1]}:`;
  }));
}

export function timingIssueTarget(issue?: string): {row: number; word: number} | null {
  const match = issue && /^Satır (\d+)(?:, kelime (\d+))?:/.exec(issue);
  return match ? {row:Number(match[1])-1, word:match[2] ? Number(match[2])-1 : 0} : null;
}

// Export unaligned lyrics at their measured row interval without inventing word times.
export function videoSegments(segments: LyricSegment[]): LyricSegment[] {
  return segments.map(instrumentalTiming).map(seg => {
    const words=seg.words||[];
    if(words.map(w=>w.word.trim()).join(' ')!==seg.text.trim().split(/\s+/).join(' '))return {...seg,words:[]};
    // A missing word must not disable every correctly measured word in the row.
    const valid=words.filter(w=>[w.start,w.end].every(Number.isFinite)&&w.start>=0&&w.end>w.start);
    return valid.length?{...seg,start:Math.min(seg.start,...valid.map(w=>w.start)),end:Math.max(seg.end,...valid.map(w=>w.end))}:seg;
  });
}

export function wordFill(word: TimedWord, time: number, previousEnd = 0, nextStart = Infinity): number {
  // Editor preview follows the stored interval, including uncertain drafts.
  // Confidence remains visible via the ? badge and is checked for export.
  if (![word.start, word.end, time].every(Number.isFinite) || word.start < 0 || word.end <= word.start
    || word.start < previousEnd - 1e-7 || word.end > nextStart + 1e-7 || time < word.start) return 0;
  return syllableFill(word,time)??Math.min(1, (time - word.start) / (word.end - word.start));
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
    ...(Array.isArray(item.repeat_cleanup)?{repeat_cleanup:item.repeat_cleanup}:{}),
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
/** Display breaks without adding artificial lyric rows or touching saved timings. */
export function soloWindows(segments: Array<{start:number;end:number;text:string;alignment_mode?:string|null}>, duration:number): Array<[number,number]> {
  if(segments.some(s=>s.alignment_mode==='supplied_ctc'))return [];
  const rows=segments.filter(s=>s.text.trim()).slice().sort((a,b)=>a.start-b.start);
  const gaps:Array<[number,number]>=[];
  let cursor=0;
  rows.forEach((row,i)=>{
    const start=Math.max(0,Math.min(duration,row.start));
    if(start-cursor>=3)gaps.push([cursor,start]);
    cursor=Math.max(cursor,Math.min(duration,row.end+(i===rows.length-1?2:.35),rows[i+1]?.start??Infinity));
  });
  if(duration-cursor>=3)gaps.push([cursor,duration]);
  return gaps;
}

export function isInstrumentalText(text:string):boolean {
  return /^\s*(solo|enstr[üu]mantal|instrumental)[.\s…!]*$/i.test(text);
}

export function rowDisplayEnd(row:LyricSegment,last:boolean,nextStart=Infinity):number {
  const music=isInstrumentalText(row.text);
  return Math.min(row.end+(music?0:last?2:.35),nextStart);
}

/** Presentation moves around the acoustic clock; it never delays that clock. */
export function rowMotion(row:LyricSegment,last:boolean,nextStart=Infinity) {
  const enter=Math.max(0,row.start-.48);
  const leave=Math.max(row.start,Math.min(row.end+(isInstrumentalText(row.text)?0:last?2:.35),nextStart)-.48);
  const fade=Math.max(row.end,leave+.48);
  return {enter,leave,fade,end:fade+.36};
}

export function rowPose(row:LyricSegment,motion:ReturnType<typeof rowMotion>,time:number) {
  if(time<motion.enter||time>=motion.end)return null;
  if(time<row.start){const p=(time-motion.enter)/Math.max(.001,row.start-motion.enter);return {offset:p-1,opacity:Math.min(1,p*2),scale:.4+.6*p};}
  const p=Math.max(0,Math.min(1,(time-motion.leave)/.48));
  return {offset:p,opacity:time<motion.fade?1:Math.max(0,1-(time-motion.fade)/.36),scale:1-.35*Math.max(0,Math.min(1,(time-Math.max(row.end,motion.leave))/.48))};
}
