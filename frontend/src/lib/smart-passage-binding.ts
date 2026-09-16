import type {LyricSegment} from './types';
import {bindDetectedWords,validRange} from './audio-passages';

type Word=NonNullable<LyricSegment['words']>[number];
type Match={index:number;start:number;end:number;score:number};
const tokens=(row:LyricSegment)=>row.text.trim().split(/\s+/).filter(Boolean);
export const isSpokenToken=(text:string)=>!!text&&!/^\p{P}+$/u.test(text);
const same=(a:string,b:string)=>a.toLocaleUpperCase('tr-TR')===b.toLocaleUpperCase('tr-TR');
const bound=(word:Word|undefined,text:string)=>!!word&&same(word.word,text)&&validRange(word.start,word.end);

export function fullyBound(row:LyricSegment):boolean {
  const text=tokens(row),words=row.words||[];
  const spoken=text.map((word,i)=>({word,i})).filter(t=>isSpokenToken(t.word));
  return spoken.length>0&&text.length===words.length&&spoken.every(({word,i},j)=>
    bound(words[i],word)&&(j===0||words[i].start>=words[spoken[j-1].i].end-1e-7));
}

// Unbound coarse timestamps that jump backwards must not block every later row.
function orderedRanges(rows:LyricSegment[]) {
  let previous=-Infinity;
  return rows.map(row=>{
    const anchored=row.locked||(row.words||[]).some(w=>validRange(w.start,w.end));
    const usable=validRange(row.start,row.end)&&(anchored||row.start>=previous-1e-7);
    if(usable)previous=Math.max(previous,row.start);
    return usable;
  });
}

export function bindingLimits(rows:LyricSegment[],index:number,duration:number) {
  const row=rows[index];let start=0,end=duration>0?duration:row.end;
  const usable=orderedRanges(rows);
  rows.forEach((other,i)=>{
    if(i===index)return;
    const words=(other.words||[]).filter(w=>validRange(w.start,w.end));
    const starts=words.map(w=>w.start),ends=words.map(w=>w.end);
    if(usable[i]){starts.push(other.start);ends.push(other.end);}
    if(i<index&&ends.length)start=Math.max(start,...ends);
    if(i>index&&starts.length)end=Math.min(end,...starts);
  });
  // Unknown adjacent timing cannot establish a safe expansion corridor.
  if(index>0&&!validRange(rows[index-1].start,rows[index-1].end))start=Math.max(start,row.start);
  if(index+1<rows.length&&!validRange(rows[index+1].start,rows[index+1].end))end=Math.min(end,row.end);
  return {start,end};
}

export async function smartBindRow(rows:LyricSegment[],index:number,duration:number,
  analyze:(row:LyricSegment)=>Promise<{word_times?:Match[]}>,signal:AbortSignal,
  progress:(attempt:number,range:{start:number;end:number})=>void) {
  const original=rows[index],text=tokens(original);
  if(original.locked||fullyBound(original))return {segment:original,attempts:0,complete:fullyBound(original),expanded:false};
  if(!text.length||!validRange(original.start,original.end)||original.end-original.start>20)
    throw Error('Önce bu satırın başlangıç ve bitişini belirleyin (en fazla 20 saniye).');
  const limits=bindingLimits(rows,index,duration);
  const hasLinks=(original.words||[]).some(w=>validRange(w.start,w.end));
  const repair=!hasLinks&&!orderedRanges(rows)[index]&&index>0&&
    validRange(limits.start,limits.end)&&limits.end-limits.start<=20&&duration>0;
  const base=repair?{...original,start:limits.start,end:limits.end}:original;
  const initial=text.map((word,i):Word=>original.words?.[i]&&same(original.words[i].word,word)?{...original.words[i]}:
    {word,start:original.start,end:original.start,timing_source:'estimated',needs_review:true});
  let best=initial;
  const count=(words:Word[])=>words.filter((w,i)=>bound(w,text[i])).length;
  let attempts=0;
  for(const padding of [0,.15,.30,.50]) {
    signal.throwIfAborted();
    const expansion=Math.min(padding,Math.max(0,(20-(base.end-base.start))/2));
    const start=Math.max(limits.start,base.start-(bound(initial[0],text[0])?0:expansion));
    const end=Math.min(limits.end,base.end+(bound(initial.at(-1),text.at(-1)!)?0:expansion));
    if(!validRange(start,end))throw Error('Bu satırın ses aralığı komşu satırla çakışıyor. Önce satır sınırlarını kontrol edin.');
    attempts++;progress(attempts,{start,end});
    // Only the target transcript is sent. Provider-generated text is never imported.
    const data=await analyze({...original,start,end});signal.throwIfAborted();
    const candidates=(data.word_times||[]).filter(t=>Number.isInteger(t.index)&&t.index>=0&&t.index<text.length&&
      Number.isFinite(t.score)&&validRange(t.start,t.end)&&t.start>=start&&t.end<=end);
    const proposed=best.map(w=>({...w}));
    text.forEach((word,i)=>{
      if(!isSpokenToken(word))return;
      if(bound(proposed[i],word))return;
      const matches=candidates.filter(t=>t.index===i);
      if(matches.length!==1)return;
      const t=matches[0];
      if(proposed.some((w,j)=>j!==i&&bound(w,text[j])&&(j<i?w.end>t.start+1e-7:w.start<t.end-1e-7)))return;
      // Use the same acceptance and preservation rules as the single-row editor.
      const linked=bindDetectedWords({...original,start,end,words:proposed},[t]).words![i];
      if(bound(linked,word))proposed[i]=linked;
    });
    const updated={...original,words:proposed};
    const linkedWords=proposed.filter(w=>validRange(w.start,w.end));
    if(fullyBound(updated))return {segment:{...updated,start:Math.min(base.start,...linkedWords.map(w=>w.start)),
      end:Math.max(base.end,...linkedWords.map(w=>w.end))},attempts,complete:true,
      expanded:proposed.some(w=>w.start<original.start||w.end>original.end)};
    // Failed expansion must not leave a wider row or a partly imported outside word.
    const safe=proposed.map((w,i)=>bound(initial[i],text[i])?initial[i]:
      (w.start>=original.start&&w.end<=original.end?w:best[i]));
    if(count(safe)>count(best))best=safe;
  }
  const changed=count(best)>count(initial);
  return {segment:changed?{...original,words:best}:original,attempts,complete:false,expanded:false};
}
