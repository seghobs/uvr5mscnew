
import { projectStorage } from '@/lib/project-storage';
import type { LyricSegment } from './types';
import { reconcileWords, uppercaseLyric } from './karaoke-timing';
export type Passage = {id:string; start:number; end:number; label:string; needs_review?:boolean; score?:number; timing_source?:NonNullable<LyricSegment['words']>[number]['timing_source']};
export type PassageDraft = {segment:LyricSegment; passages:Passage[]};
export function uniquePassages(passages:Passage[]):Passage[] {
  const byId=new Map<string,Passage>();
  for(const passage of passages){
    let id=passage.id, suffix=1;
    let existing=byId.get(id);
    // Keep distinct intervals selectable even if an older edit reused an ID.
    while(existing&&(existing.start!==passage.start||existing.end!==passage.end)){
      id=`${passage.id}:duplicate:${suffix++}`;
      existing=byId.get(id);
    }
    byId.set(id,existing
      ? {...existing,needs_review:existing.needs_review||passage.needs_review}
      : {...passage,id});
  }
  return [...byId.values()];
}
export const validRange = (s:number,e:number) => Number.isFinite(s) && Number.isFinite(e) && s>=0 && e>s;
export function passagePool(segment:LyricSegment):Passage[] {
  return (segment.words || []).filter(w=>validRange(w.start,w.end)).map((w,i)=>({id:`${i}:${w.start}:${w.end}`,start:w.start,end:w.end,label:w.word,needs_review:w.needs_review,timing_source:w.timing_source}));
}
export function poolKey(file:string,row:number,start:number,rowId?:string) { return rowId?`uvr-passages-v3:${file}:${rowId}`:`uvr-passages-v2:${file}:${row}:${start}`; }
export function preservePassages(file:string,row:number,segment:LyricSegment) {
  try {
    const key=poolKey(file,row,segment.start,segment.id);
    if (!projectStorage.getItem(key)) projectStorage.setItem(key,JSON.stringify(passagePool(segment)));
  } catch { /* Storage can be unavailable; the editor still works in memory. */ }
}
export function editPassageText(draft:PassageDraft,text:string):PassageDraft {
  const next=uppercaseLyric(text);
  return {...draft,segment:{...draft.segment,text:next,words:reconcileWords(draft.segment.words || [],next,draft.segment.start)}};
}
export function bindPassage(draft:PassageDraft,id:string,index:number):PassageDraft {
  const clip=draft.passages.find(p=>p.id===id);
  if (!clip || !validRange(clip.start,clip.end)) throw Error('Önce geçerli bir ses parçası seçin.');
  const words=(draft.segment.words || []).map(w=>({...w}));
  if (!words[index]) throw Error('Kelime bulunamadı.');
  const before=words.slice(0,index).filter(w=>validRange(w.start,w.end));
  const after=words.slice(index+1).filter(w=>validRange(w.start,w.end));
  if (before.some(w=>w.end>clip.start+1e-7) || after.some(w=>w.start<clip.end-1e-7)) {
    throw Error('Bu bağlantı kelime sırasını bozuyor veya başka kelimeyle çakışıyor. İlgili eski bağlantıyı kaldırın.');
  }
  words[index]={...words[index],start:clip.start,end:clip.end,timing_source:'manual',needs_review:!!clip.needs_review};
  return {...draft,segment:{...draft.segment,words,start:Math.min(draft.segment.start,clip.start),end:Math.max(draft.segment.end,clip.end)}};
}
export function bindAllPassages(draft:PassageDraft):PassageDraft {
  const tokens=draft.segment.text.trim().split(/\s+/).filter(Boolean);
  const clips=[...draft.passages].sort((a,b)=>a.start-b.start || a.end-b.end)
    .filter((p,i,list)=>i===0 || p.start!==list[i-1].start || p.end!==list[i-1].end);
  if(!tokens.length || !clips.length)throw Error('Bağlamak için söz ve ses parçaları gerekli.');
  if(clips.some((p,i)=>!validRange(p.start,p.end)||(i>0&&p.start<clips[i-1].end-1e-7)))
    throw Error('Ses parçaları çakışıyor. Alternatif kayıtları tek tek kelimelere bağlayın.');
  if(clips.length!==tokens.length)throw Error(`${tokens.length} kelime ve ${clips.length} ses parçası var. Önce parçaları bölerek/birleştirerek kelime sayısıyla eşleştirin veya tek tek bağlayın.`);
  const words=tokens.map((word,i)=>({word,start:clips[i].start,end:clips[i].end,timing_source:clips[i].timing_source ?? 'manual' as const,needs_review:!!clips[i].needs_review}));
  return {...draft,segment:{...draft.segment,words,start:clips[0].start,end:clips.at(-1)!.end}};
}

export function bindAllRows(segments:LyricSegment[], pools:Passage[][]) {
  const problems:string[]=[];
  let count=0;
  const result=segments.map((segment,index)=>{
    try {
      // Prefer the current assigned intervals over historical/alternative clips.
      const current=passagePool(segment);
      const expected=segment.text.trim().split(/\s+/).filter(Boolean).length;
      const passages=current.length===expected ? current : pools[index] || current;
      if(!passages.length&&expected&&validRange(segment.start,segment.end))
        throw Error('Satır süresi kayıtlı ve korundu. Ayrı kelime süreleri henüz yok; “Ses parçalarını bağla” ekranından sesten bulup uygulayın.');
      const updated=bindAllPassages({segment,passages}).segment;
      const previous=segments[index-1],next=segments[index+1];
      if((previous&&validRange(previous.start,previous.end)&&updated.start<previous.end-1e-7) ||
        (next&&validRange(next.start,next.end)&&updated.end>next.start+1e-7))throw Error('Ses aralığı komşu satırla çakışıyor.');
      count++;
      return updated;
    }catch(error){problems.push(`Satır ${index+1}: ${(error as Error).message}`);return segment;}
  });
  return {segments:result,count,problems};
}

export function bindDetectedSyllables(segment:LyricSegment, passages:Passage[]):LyricSegment {
  const tokens=segment.text.trim().split(/\s+/).filter(Boolean);
  const words=tokens.map((word,index)=>{
    const clips=passages.filter(p=>p.id.startsWith(`auto:${index}:`)).sort((a,b)=>a.start-b.start);
    if(!clips.length)throw Error('Bazı kelimeler seste güvenilir biçimde bulunamadı; satır korundu.');
    const start=clips[0].start,end=clips.at(-1)!.end;
    if(!validRange(start,end)||start<segment.start||end>segment.end)throw Error('Bulunan ses satır sınırını aşıyor.');
    return {word,start,end,timing_source:'ctc' as const,needs_review:true};
  });
  if(words.some((w,i)=>i>0&&w.start<words[i-1].end))throw Error('Bulunan kelimeler çakışıyor.');
  return {...segment,words};
}

export function bindDetectedWords(segment:LyricSegment, times:Array<{index:number;start:number;end:number}>):LyricSegment {
  const words=segment.text.trim().split(/\s+/).filter(Boolean).map((word,index)=>{
    const old=segment.words?.[index];
    if(old?.word===word&&validRange(old.start,old.end)&&old.timing_source==='manual')return {...old};
    const time=times.find(t=>t.index===index);
    if(time&&validRange(time.start,time.end)&&time.start>=segment.start&&time.end<=segment.end)
      return {word,start:time.start,end:time.end,timing_source:'ctc' as const,needs_review:true};
    return {word,start:segment.start,end:segment.start,timing_source:'estimated' as const,needs_review:true};
  });
  let previousEnd=segment.start;
  for(const word of words){if(!validRange(word.start,word.end))continue;if(word.start<previousEnd)throw Error('Bulunan kelimeler çakışıyor.');previousEnd=word.end;}
  return {...segment,words};
}
export function splitPassage(draft:PassageDraft,id:string,at:number):PassageDraft {
  const clip=draft.passages.find(p=>p.id===id);
  if (!clip || !Number.isFinite(at) || at<=clip.start || at>=clip.end) throw Error('Bölme noktası parçanın içinde olmalı.');
  return {...draft,passages:draft.passages.flatMap(p=>p.id===id ? [
    {...p,id:p.id+':a',end:at,label:p.label+' · 1'}, {...p,id:p.id+':b',start:at,label:p.label+' · 2'}] : [p])};
}
export function splitAndBindPassage(draft:PassageDraft,id:string,at:number,index:number,first:string,second:string):PassageDraft {
  const clip=draft.passages.find(p=>p.id===id);
  if(!clip||!validRange(clip.start,at)||!validRange(at,clip.end))throw Error('Bölme noktası seçili parçanın içinde olmalı.');
  const labels=[first,second].map(s=>uppercaseLyric(s.trim()));
  if(labels.some(s=>!s||/\s/.test(s)))throw Error('İki kutuya birer kelime yazın.');
  const tokens=draft.segment.text.trim().split(/\s+/).filter(Boolean);
  if(!Number.isInteger(index)||index<0||index>=tokens.length)throw Error('Yerine iki kelime yazılacak kelimeyi seçin.');
  const words=reconcileWords(draft.segment.words||[],draft.segment.text,draft.segment.start);
  if(words.some((w,i)=>i!==index&&validRange(w.start,w.end)&&(i<index?w.end>clip.start+1e-7:w.start<clip.end-1e-7)))
    throw Error('Seçili ses başka kelimenin bağlantısıyla çakışıyor. Doğru kelimeyi seçin veya çakışan bağlantıyı kaldırın.');
  const used=new Set(draft.passages.map(p=>p.id));
  const clips=labels.map((label,i)=>{
    let nextId=`${id}:split:${i}`,suffix=1;
    while(used.has(nextId))nextId=`${id}:split:${i}:${suffix++}`;
    used.add(nextId);
    return {...clip,id:nextId,label,start:i===0?clip.start:at,end:i===0?at:clip.end,timing_source:'manual' as const};
  });
  words.splice(index,1,...clips.map(p=>({word:p.label,start:p.start,end:p.end,timing_source:p.timing_source,needs_review:!!p.needs_review})));
  tokens.splice(index,1,...labels);
  return {segment:{...draft.segment,text:tokens.join(' '),words,start:Math.min(draft.segment.start,clip.start),end:Math.max(draft.segment.end,clip.end)},
    passages:draft.passages.filter(p=>p.id!==id).concat(clips)};
}
export function mergePassages(draft:PassageDraft,id:string):PassageDraft {
  const sorted=[...draft.passages].sort((a,b)=>a.start-b.start);
  const index=sorted.findIndex(p=>p.id===id),left=sorted[index],right=sorted[index+1];
  if (!left || !right || Math.abs(left.end-right.start)>1e-7) throw Error('Yalnızca sınırları bitişik parçalar birleşir; sessiz boşluklar korunur.');
  return {...draft,passages:draft.passages.filter(p=>p.id!==left.id&&p.id!==right.id).concat({id:left.id+'+'+right.id,start:left.start,end:right.end,label:left.label+' + '+right.label,needs_review:!!(left.needs_review||right.needs_review),timing_source:left.timing_source===right.timing_source?left.timing_source:undefined})};
}
// Correct recognition text while retaining the original ordered audio intervals.
export function correctedCandidateWords(text: string, source: NonNullable<LyricSegment['words']>): NonNullable<LyricSegment['words']> {
  return text.toLocaleUpperCase('tr-TR').trim().split(/\s+/).filter(Boolean).map((word, index) => {
    const interval = source[index];
    return interval ? {...interval, word, needs_review:true} : {
      word, start:source.at(-1)?.end ?? 0, end:source.at(-1)?.end ?? 0,
      timing_source:'estimated' as const, needs_review:true,
    };
  });
}
