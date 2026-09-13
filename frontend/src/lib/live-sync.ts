import type {LyricSegment} from './types';

export function clearLiveTimings(segments: LyricSegment[]): LyricSegment[] {
  // A zero-length interval is the existing unaligned sentinel, never playable.
  return segments.map(segment => segment.locked?segment:({...segment, start:0, end:0,
    words:segment.text.trim().split(/\s+/).filter(Boolean).map(word => ({
      word, start:0, end:0, timing_source:'estimated' as const, needs_review:true,
    })),
  }));
}

export function recordLiveRow(segment:LyricSegment,start:number,end:number):LyricSegment {
  if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start)throw Error('Geçerli bir başlangıç ve bitiş kaydedilemedi.');
  // Even a partially linked row is protected. Only explicit unlink/reset actions
  // may discard measured word intervals; passing through live sync must not.
  if(segment.locked)return segment;
  if(segment.words?.some(word=>Number.isFinite(word.start)&&Number.isFinite(word.end)&&word.start>=0&&word.end>word.start))return segment;
  // An unlinked row can receive new row boundaries without inventing word times.
  return {...segment,start,end,words:segment.text.trim().split(/\s+/).filter(Boolean).map(word=>({word,start,end:start,timing_source:'estimated',needs_review:true}))};
}
