
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

export function addApprovedPassage(draft:PassageDraft,id:string,start:number,end:number,duration:number,text:string):PassageDraft {
  const label=uppercaseLyric(text.trim().replace(/\s+/g,' '));
  if(!label||!validRange(start,end)||!Number.isFinite(duration)||duration<=0||end>duration)throw Error('Geçerli bir söz ve ses dosyası içinde bir aralık gerekli.');
  const same=(p:Passage)=>Math.abs(p.start-start)<1e-7&&Math.abs(p.end-end)<1e-7&&uppercaseLyric(p.label)===label;
  const existing=draft.passages.find(same);
  const approved:Passage={id:existing?.id||id,start,end,label,timing_source:'manual',needs_review:false};
  if(!existing&&draft.passages.some(p=>p.id===id))throw Error('Parça kimliği kullanılıyor. Tekrar deneyin.');
  return {segment:draft.segment,passages:[...draft.passages.filter(p=>!same(p)),approved]};
}

// Edit only the selected clip and its unambiguous, exact existing word link.
export function revisePassage(draft:PassageDraft,id:string,start:number,end:number,duration:number,text?:string,recognized:NonNullable<LyricSegment['words']>=[]):PassageDraft {
  const clip=draft.passages.find(p=>p.id===id);
  if(!clip||!validRange(start,end)||!Number.isFinite(duration)||duration<=0||end>duration)throw Error('Ses dosyası içinde geçerli bir başlangıç ve bitiş girin.');
  const label=text===undefined?clip.label:uppercaseLyric(text.trim().replace(/\s+/g,' '));
  if(!label)throw Error('Onaylanacak söz boş olamaz.');
  const words=(draft.segment.words||[]).map(w=>({...w}));
  const links=words.map((w,i)=>({w,i})).filter(({w})=>Math.abs(w.start-clip.start)<1e-7&&Math.abs(w.end-clip.end)<1e-7);
  if(links.length>1)throw Error('Bu parça birden fazla kelimeye bağlı; önce bağlantıları kontrol edin.');
  let segment=draft.segment;
  if(links.length===1){
    if(words.map(w=>w.word.trim()).join(' ')!==draft.segment.text.trim().replace(/\s+/g,' '))throw Error('Satır metni ile bağlantılar uyuşmuyor. Önce kelime bağlantılarını kontrol edin.');
    const index=links[0].i;
    if(words.some((w,j)=>j!==index&&validRange(w.start,w.end)&&(j<index?w.end>start+1e-7:w.start<end-1e-7)))
      throw Error('Yeni aralık komşu kelimeyle çakışıyor. Diğer bağlantılar korundu.');
    // Auto-resolve boundary overlaps with adjacent words in same row
    for (let j = 0; j < index; j++) {
      if (words[j] && validRange(words[j].start, words[j].end) && words[j].end > start) {
        words[j].end = Number(Math.max(words[j].start + 0.05, start - 0.01).toFixed(3));
      }
    }
    for (let j = index + 1; j < words.length; j++) {
      if (words[j] && validRange(words[j].start, words[j].end) && words[j].start < end) {
        words[j].start = Number((end + 0.01).toFixed(3));
        if (words[j].end <= words[j].start + 0.05) {
          words[j].end = Number((words[j].start + 0.08).toFixed(3));
        }
      }
    }
    let replacement:NonNullable<LyricSegment['words']>;
    if(text===undefined)replacement=[{...words[index],start,end,timing_source:'manual'}];
    else if(!label.includes(' '))replacement=[{word:label,start,end,timing_source:'manual',needs_review:false}];
    else {
      if(recognized.some(w=>!validRange(w.start,w.end)||w.start<start||w.end>end))throw Error('Önerinin kelime süreleri seçili aralığın dışında.');
      replacement=correctedCandidateWords(label,recognized);
      // Auto-sequence any overlapping candidates
      for (let k = 1; k < replacement.length; k++) {
        if (validRange(replacement[k].start, replacement[k].end) && replacement[k].start < replacement[k - 1].end) {
          replacement[k].start = Number((replacement[k - 1].end + 0.01).toFixed(3));
          if (replacement[k].end <= replacement[k].start + 0.05) {
            replacement[k].end = Number((replacement[k].start + 0.08).toFixed(3));
          }
        }
      }
    }
    words.splice(index,1,...replacement);
    segment={...segment,words,text:words.map(w=>w.word).join(' '),start:Math.min(segment.start,start),end:Math.max(segment.end,end)};
  }
  return {segment,passages:draft.passages.map(p=>p.id===id?{...p,start,end,label,timing_source:'manual',needs_review:text===undefined?p.needs_review:false}:p)};
}
// Automatically resolve boundary collisions and overlap with neighbouring rows continuously without throwing errors.
export function fitPassageRow(segments:LyricSegment[],index:number,updated:LyricSegment,trimToNeighbours=false):{segment:LyricSegment;adjusted:number;allSegments:LyricSegment[]} {
  // Never alter a neighbouring row while repairing this one. A clip with no
  // usable space is unlinked for review instead of receiving invented timing.
  const neighbours=segments.flatMap((segment,row)=>row===index?[]:(segment.words||[])
    .filter(word=>validRange(word.start,word.end)).map(word=>({row,word})));
  const previous=neighbours.filter(item=>item.row<index).sort((a,b)=>b.word.end-a.word.end)[0];
  const next=neighbours.filter(item=>item.row>index).sort((a,b)=>a.word.start-b.word.start)[0];
  let repaired=0;
  const repairedWords=(updated.words||[]).map(word=>{
    if(!validRange(word.start,word.end))return {...word};
    const start=Math.max(word.start,previous?.word.end??0);
    const end=Math.min(word.end,next?.word.start??Infinity);
    const overlap=Math.max(start-word.start,word.end-end);
    if(overlap<=1e-7)return {...word};
    if(!trimToNeighbours&&overlap>.0300001){
      const conflict=start>word.start+1e-7?previous!:next!;
      throw Error(`“${word.word}” bağlantısı ${conflict.row+1}. satırdaki “${conflict.word.word}” ile ${Math.round(overlap*1000)} ms çakışıyor. “Taşan bağlantıları bu satıra sığdır” ile başlangıç/bitişi düzeltebilirsiniz. Diğer satır korundu.`);
    }
    repaired++;
    if(end-start<.02){
      if(!trimToNeighbours)throw Error(`“${word.word}” parçası komşu satırın içinde kalıyor. Bu kelime için başka bir ses parçası seçin; mevcut bağlantılar korundu.`);
      return {...word,start:0,end:0,timing_source:'estimated' as const,needs_review:true};
    }
    return {...word,start,end,needs_review:true};
  });
  const linked=repairedWords.filter(word=>validRange(word.start,word.end));
  const segment={...updated,words:repairedWords,
    start:linked.length?Math.min(...linked.map(word=>word.start)):updated.start,
    end:linked.length?Math.max(...linked.map(word=>word.end)):updated.end};
  return {segment,adjusted:repaired,allSegments:segments.map((item,row)=>row===index?segment:item)};

  /* Legacy boundary-repair implementation kept out of execution while this
     migration is verified. It moved neighbouring rows and could invent time.
  const allSegments = segments.map((s, i) => i === index ? cloneSegment(updated) : cloneSegment(s));
  let adjusted = 0;
  const currentWords = (updated.words || []).filter(w => w && typeof w.word === 'string').map(w => ({ ...w }));

  if (currentWords.length === 0) {
    return { segment: { ...updated }, adjusted: 0, allSegments };
  }

  // 1. Ensure internal word order and valid durations within the current row
  for (let i = 0; i < currentWords.length; i++) {
    const w = currentWords[i];
    if (!validRange(w.start, w.end)) {
      const prevEnd = i > 0 && validRange(currentWords[i - 1].start, currentWords[i - 1].end)
        ? currentWords[i - 1].end
        : (Number.isFinite(w.start) ? w.start : updated.start);
      w.start = Number(prevEnd.toFixed(3));
      w.end = Number((w.start + 0.3).toFixed(3));
      adjusted++;
    }
    if (w.end < w.start + 0.05) {
      w.end = Number((w.start + 0.08).toFixed(3));
      adjusted++;
    }
    if (i > 0 && w.start < currentWords[i - 1].end) {
      const prev = currentWords[i - 1];
      if (prev.end - prev.start > 0.15) {
        prev.end = Number(Math.max(prev.start + 0.05, w.start).toFixed(3));
      } else {
        w.start = Number(prev.end.toFixed(3));
        if (w.end <= w.start + 0.05) {
          w.end = Number((w.start + 0.08).toFixed(3));
        }
      }
      adjusted++;
    }
  }

  // 2. Resolve boundary with PRECEDING neighbour rows (rows < index)
  let prevRowIdx = -1;
  for (let r = index - 1; r >= 0; r--) {
    if (allSegments[r] && (validRange(allSegments[r].start, allSegments[r].end) || (allSegments[r].words || []).some(w => validRange(w.start, w.end)))) {
      prevRowIdx = r;
      break;
    }
  }

  if (prevRowIdx >= 0) {
    const prevSeg = allSegments[prevRowIdx];
    const prevWords = (prevSeg.words || []).filter(w => validRange(w.start, w.end));
    const firstWord = currentWords[0];
    const prevEnd = prevWords.length > 0 ? prevWords[prevWords.length - 1].end : prevSeg.end;

    if (prevEnd > firstWord.start) {
      adjusted++;
      if (prevWords.length > 0) {
        const lastPrevWord = prevWords[prevWords.length - 1];
        if (firstWord.start > lastPrevWord.start + 0.08) {
          lastPrevWord.end = Number(Math.max(lastPrevWord.start + 0.05, firstWord.start - 0.01).toFixed(3));
          prevSeg.end = lastPrevWord.end;
        } else {
          // Corridor split: share interval cleanly so neither word is swallowed
          const corridorStart = Math.min(lastPrevWord.start, firstWord.start);
          const corridorEnd = Math.max(lastPrevWord.end, firstWord.end);
          const mid = Number((corridorStart + (corridorEnd - corridorStart) * 0.45).toFixed(3));
          lastPrevWord.start = corridorStart;
          lastPrevWord.end = Number(Math.max(corridorStart + 0.05, mid - 0.01).toFixed(3));
          prevSeg.end = lastPrevWord.end;

          firstWord.start = Number(mid.toFixed(3));
          if (firstWord.end <= firstWord.start + 0.05) {
            firstWord.end = Number((firstWord.start + Math.max(0.1, corridorEnd - mid)).toFixed(3));
          }
        }
        prevSeg.words = prevWords;
      } else {
        prevSeg.end = Number(Math.max(prevSeg.start + 0.1, firstWord.start - 0.01).toFixed(3));
      }
    }
  }

  // 3. Resolve boundary with SUCCEEDING neighbour rows (rows > index)
  let nextRowIdx = -1;
  for (let r = index + 1; r < allSegments.length; r++) {
    if (allSegments[r] && (validRange(allSegments[r].start, allSegments[r].end) || (allSegments[r].words || []).some(w => validRange(w.start, w.end)))) {
      nextRowIdx = r;
      break;
    }
  }

  if (nextRowIdx >= 0) {
    const nextSeg = allSegments[nextRowIdx];
    const nextWords = (nextSeg.words || []).filter(w => validRange(w.start, w.end));
    const lastWord = currentWords[currentWords.length - 1];
    const nextStart = nextWords.length > 0 ? nextWords[0].start : nextSeg.start;

    if (lastWord.end > nextStart) {
      adjusted++;
      if (nextWords.length > 0) {
        const firstNextWord = nextWords[0];
        if (firstNextWord.end > lastWord.end + 0.08) {
          firstNextWord.start = Number((lastWord.end + 0.01).toFixed(3));
          nextSeg.start = firstNextWord.start;
        } else {
          const corridorStart = Math.min(lastWord.start, firstNextWord.start);
          const corridorEnd = Math.max(lastWord.end, firstNextWord.end);
          const mid = Number((corridorStart + (corridorEnd - corridorStart) * 0.55).toFixed(3));
          lastWord.end = Number(Math.max(lastWord.start + 0.05, mid - 0.01).toFixed(3));
          firstNextWord.start = Number(mid.toFixed(3));
          firstNextWord.end = Number(Math.max(firstNextWord.start + 0.08, corridorEnd).toFixed(3));
          nextSeg.start = firstNextWord.start;
        }
        nextSeg.words = nextWords;
      } else {
        nextSeg.start = Number((lastWord.end + 0.01).toFixed(3));
        if (nextSeg.end <= nextSeg.start) {
          nextSeg.end = Number((nextSeg.start + 2.0).toFixed(3));
        }
      }
    }
  }

  // 4. Final verification of current row words
  for (let i = 0; i < currentWords.length; i++) {
    const w = currentWords[i];
    if (w.end < w.start + 0.05) {
      w.end = Number((w.start + 0.08).toFixed(3));
    }
    if (i < currentWords.length - 1 && w.end > currentWords[i + 1].start) {
      currentWords[i + 1].start = Number(w.end.toFixed(3));
      if (currentWords[i + 1].end <= currentWords[i + 1].start + 0.05) {
        currentWords[i + 1].end = Number((currentWords[i + 1].start + 0.08).toFixed(3));
      }
    }
  }

  const finalStart = currentWords.length > 0 ? currentWords[0].start : updated.start;
  const finalEnd = currentWords.length > 0 ? currentWords[currentWords.length - 1].end : updated.end;

  const fittedSegment: LyricSegment = {
    ...updated,
    words: currentWords,
    start: finalStart,
    end: finalEnd,
  };
  allSegments[index] = fittedSegment;

  return { segment: fittedSegment, adjusted, allSegments };
}
  */
}

export function passagePool(segment:LyricSegment):Passage[] {
  return (segment.words || []).filter(w=>validRange(w.start,w.end)).map((w,i)=>({id:`${i}:${w.start}:${w.end}`,start:w.start,end:w.end,label:w.word,needs_review:w.needs_review,timing_source:w.timing_source}));
}
export function poolKey(file:string,row:number,start:number,rowId?:string) { return rowId?`uvr-passages-v3:${file}:${rowId}`:`uvr-passages-v2:${file}:${row}:${start}`; }

export function clearRowPassages(file:string,row:number,segment:LyricSegment) {
  // Remove every cached audio-passage pool entry for this row so a cleared
  // row does not resurrect old clips from projectStorage. Covers both the
  // id-based v3 key and any legacy v2 keys (row + start variants).
  try {
    const prefixV2=`uvr-passages-v2:${file}:${row}:`;
    for(const key of projectStorage.keys()){
      if(key===poolKey(file,row,segment.start,segment.id)||key.startsWith(prefixV2))projectStorage.removeItem(key);
    }
  } catch { /* Storage can be unavailable; the editor still works in memory. */ }
}
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
  if(before.some(w=>w.end>clip.start+1e-7)||after.some(w=>w.start<clip.end-1e-7))
    throw Error('Bu bağlantı kelime sırasını bozuyor veya başka kelimeyle çakışıyor. İlgili eski bağlantıyı kaldırın.');

  // Auto-resolve boundary overlaps with adjacent words in the line
  for (let i = 0; i < index; i++) {
    if (words[i] && validRange(words[i].start, words[i].end) && words[i].end > clip.start) {
      words[i].end = Number(Math.max(words[i].start + 0.05, clip.start - 0.01).toFixed(3));
    }
  }
  for (let i = index + 1; i < words.length; i++) {
    if (words[i] && validRange(words[i].start, words[i].end) && words[i].start < clip.end) {
      words[i].start = Number((clip.end + 0.01).toFixed(3));
      if (words[i].end <= words[i].start + 0.05) {
        words[i].end = Number((words[i].start + 0.08).toFixed(3));
      }
    }
  }

  words[index]={...words[index],start:clip.start,end:clip.end,timing_source:'manual',needs_review:!!clip.needs_review};
  return {...draft,segment:{...draft.segment,words,start:Math.min(draft.segment.start,clip.start),end:Math.max(draft.segment.end,clip.end)}};
}
export function bindAllPassages(draft:PassageDraft):PassageDraft {
  const tokens=draft.segment.text.trim().split(/\s+/).filter(Boolean);
  const clips=[...draft.passages].sort((a,b)=>a.start-b.start || a.end-b.end)
    .filter((p,i,list)=>i===0 || p.start!==list[i-1].start || p.end!==list[i-1].end);
  if(!tokens.length || !clips.length)throw Error('Bağlamak için söz ve ses parçaları gerekli.');
  if(clips.some((clip,i)=>!validRange(clip.start,clip.end)||(i>0&&clip.start<clips[i-1].end-1e-7)))
    throw Error('Ses parçaları çakışıyor. Alternatif kayıtları tek tek kelimelere bağlayın.');
  // Auto-resolve overlapping clips smoothly
  for (let i = 1; i < clips.length; i++) {
    if (clips[i].start < clips[i - 1].end) {
      const mid = Number(((clips[i - 1].end + clips[i].start) / 2).toFixed(3));
      clips[i - 1].end = Number(Math.max(clips[i - 1].start + 0.05, mid - 0.01).toFixed(3));
      clips[i].start = Number(Math.max(clips[i - 1].end, mid).toFixed(3));
      if (clips[i].end <= clips[i].start + 0.05) {
        clips[i].end = Number((clips[i].start + 0.08).toFixed(3));
      }
    }
  }
  if(clips.length!==tokens.length)throw Error(`${tokens.length} kelime ve ${clips.length} ses parçası var. Önce parçaları bölerek/birleştirerek kelime sayısıyla eşleştirin veya tek tek bağlayın.`);
  const words=tokens.map((word,i)=>({word,start:clips[i].start,end:clips[i].end,timing_source:clips[i].timing_source ?? 'manual' as const,needs_review:!!clips[i].needs_review}));
  return {...draft,segment:{...draft.segment,words,start:clips[0].start,end:clips.at(-1)!.end}};
}

export function bindAllRows(segments:LyricSegment[], pools:Passage[][]) {
  const problems:string[]=[];
  let count=0;
  const result=segments.map((segment,index)=>{
    if(segment.locked)return segment;
    try {
      // Prefer the current assigned intervals over historical/alternative clips.
      const current=passagePool(segment);
      const expected=segment.text.trim().split(/\s+/).filter(Boolean).length;
      const passages=current.length===expected ? current : pools[index] || current;
      if(!passages.length&&expected&&validRange(segment.start,segment.end))
        throw Error('Satır süresi kayıtlı ve korundu. Ayrı kelime süreleri henüz yok; “Ses parçalarını bağla” ekranından sesten bulup uygulayın.');
      const updated=bindAllPassages({segment,passages}).segment;
      // Auto-fit against neighbour rows continuously
      const fitted=fitPassageRow(segments,index,updated,true);
      count++;
      return fitted.segment;
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
  // Auto-resolve overlapping words
  for (let i = 1; i < words.length; i++) {
    if (words[i].start < words[i - 1].end) {
      words[i].start = Number((words[i - 1].end + 0.01).toFixed(3));
      if (words[i].end <= words[i].start + 0.05) {
        words[i].end = Number((words[i].start + 0.08).toFixed(3));
      }
    }
  }
  return {...segment,words};
}

export function bindDetectedWords(segment:LyricSegment, times:Array<{index:number;start:number;end:number;score?:number}>):LyricSegment {
  const words=segment.text.trim().split(/\s+/).filter(Boolean).map((word,index)=>{
    const old=segment.words?.[index];
    if(old?.word.toLocaleUpperCase('tr-TR')===word.toLocaleUpperCase('tr-TR')&&validRange(old.start,old.end))return {...old};
    const time=times.find(t=>t.index===index);
    if(time&&(time.score===undefined||(Number.isFinite(time.score)&&time.score>=.15))&&validRange(time.start,time.end)&&time.start>=segment.start&&time.end<=segment.end)
      return {word,start:time.start,end:time.end,timing_source:'ctc' as const,needs_review:true,...(time.score===undefined?{}:{probability:time.score})};
    return {word,start:segment.start,end:segment.start,timing_source:'estimated' as const,needs_review:true};
  });
  let previousEnd=segment.start;
  for(const word of words){
    if(!validRange(word.start,word.end))continue;
    if(word.start<previousEnd) {
      word.start = Number((previousEnd + 0.01).toFixed(3));
      if (word.end <= word.start + 0.05) {
        word.end = Number((word.start + 0.08).toFixed(3));
      }
    }
    previousEnd=word.end;
  }
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
