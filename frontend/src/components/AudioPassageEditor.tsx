'use client';

import { projectStorage } from '@/lib/project-storage';

import {StudioSelect} from './StudioSelect';
import {updateLyricInput} from '@/lib/lyric-input';
import React,{useEffect,useRef,useState} from 'react';
import type {LyricSegment} from '@/lib/types';
import {WordPlayer} from '@/lib/word-player';
type WordCandidate={label:string;text:string;words:NonNullable<LyricSegment['words']>;agreement:number};
import {bindAllPassages,bindDetectedWords,correctedCandidateWords,passagePool,poolKey,uniquePassages,validRange,editPassageText,bindPassage,splitPassage,splitAndBindPassage,mergePassages,type PassageDraft,type Passage} from '@/lib/audio-passages';

export function AudioPassageEditor({file,row,segment,onClose,onApply,onFit}:{file:string;row:number;segment:LyricSegment;onClose:()=>void;onApply:(segment:LyricSegment)=>void;onFit?:(segment:LyricSegment)=>LyricSegment}) {
  const [draft,setDraft]=useState<PassageDraft>(()=>{
    let passages=passagePool(segment);
    try {const stored=JSON.parse(projectStorage.getItem(poolKey(file,row,segment.start,segment.id)) || projectStorage.getItem(poolKey(file,row,segment.start)) || 'null');
      if(Array.isArray(stored)) {
        const safe=stored.filter(p=>p&&typeof p.id==='string'&&typeof p.label==='string'&&validRange(p.start,p.end));
        passages=[...safe,...passages.filter(p=>!safe.some(q=>q.start===p.start&&q.end===p.end))];
      }
    } catch {}
    return {segment:structuredClone(segment),passages:uniquePassages(passages)};
  });
  const [history,setHistory]=useState<PassageDraft[]>([]);
  const [selected,setSelected]=useState('');
  const [splitTarget,setSplitTarget]=useState(-1);
  const [firstWord,setFirstWord]=useState('');
  const [secondWord,setSecondWord]=useState('');
  const selectedClip=draft.passages.find(p=>p.id===selected);
  const [cursor,setCursor]=useState(segment.start);
  const [rangeStart,setRangeStart]=useState(segment.start);
  const [rangeEnd,setRangeEnd]=useState(segment.end);
  const [peaks,setPeaks]=useState<number[]>([]);
  const [duration,setDuration]=useState(0);
  const [error,setError]=useState('');
  const [playing,setPlaying]=useState(false);
  const [detecting,setDetecting]=useState(false);
  const [notice,setNotice]=useState('');
  const [finding,setFinding]=useState(false);
  const [candidates,setCandidates]=useState<WordCandidate[]>([]);
  const candidateRevision=useRef(0);
  const revision=useRef(0);
  const detection=useRef<AbortController|null>(null);
  useEffect(()=>()=>{detection.current?.abort();},[]);
  const player=useRef<WordPlayer|null>(null);
  const sequence=useRef(0);
  const left=Math.max(0,Math.min(segment.start,...draft.passages.map(p=>p.start))-1);
  const right=Math.min(duration || Infinity,Math.max(segment.end,...draft.passages.map(p=>p.end),left+1)+1);
  useEffect(()=>{
    const audio=new WordPlayer();player.current=audio;let live=true;
    audio.prepare(`/output/${encodeURIComponent(file)}`).then(buffer=>{
      if(!live)return;setDuration(buffer.duration);
      const channel=buffer.getChannelData(0),values=[];
      const start=Math.floor(left*buffer.sampleRate),stop=Math.min(channel.length,Math.ceil(right*buffer.sampleRate));
      for(let i=0;i<400;i++) {let peak=0;const a=start+Math.floor((stop-start)*i/400),b=start+Math.floor((stop-start)*(i+1)/400);
        for(let j=a;j<b;j++) peak=Math.max(peak,Math.abs(channel[j]));values.push(peak);}
      setPeaks(values);
    }).catch(e=>{if(live)setError(e.message);});
    return ()=>{live=false;sequence.current++;audio.dispose();};
  },[file,left,right]);
  const change=(update:(value:PassageDraft)=>PassageDraft)=>{
    try {const next=update(draft);player.current?.stop();sequence.current++;setPlaying(false);
      revision.current++;
      setHistory(h=>[...h.slice(-49),structuredClone(draft)]);setDraft({...next,passages:uniquePassages(next.passages)});setError('');
    } catch(e){setError((e as Error).message);}
  };
  const detect=async(bindWords=false)=>{
    if(!validRange(rangeStart,rangeEnd)||rangeEnd-rangeStart>20||(duration&&rangeEnd>duration)){setError('Hizalama için ses içinde en fazla 20 saniyelik bir aralık seçin.');return;}
    const target={...draft.segment,start:rangeStart,end:rangeEnd};
    const controller=new AbortController();detection.current=controller;
    const version=revision.current;setDetecting(true);setError('');setNotice('');
    try {
      const response=await fetch('/api/lyrics/syllables',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file_name:file,segment:target}),signal:controller.signal});
      const data=await response.json();
      if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Hece tespiti tamamlanamadı.');
      if(version!==revision.current)throw Error('İşlem sırasında düzenleme yapıldı. Yeni değişiklikler korundu; hece tespitini tekrar başlatın.');
      const clips:Passage[]=data.passages;
      if(!Array.isArray(clips)||clips.some(p=>!validRange(p.start,p.end)||typeof p.id!=='string'||typeof p.label!=='string'))throw Error('Geçersiz hece sonucu; mevcut parçalar korundu.');
      if(bindWords){
        const times=data.word_times;
        if(!Array.isArray(times)||!times.some(t=>Number.isInteger(t.index)&&validRange(t.start,t.end)))
          throw Error('Yazdığın sözler için güvenilir kelime sınırı bulunamadı. Satırın ses aralığını kontrol et veya parçaları elle bağla; mevcut bağlantılar korundu.');
        const updated=bindDetectedWords(target,times);
        const missing=(updated.words||[]).filter(w=>!validRange(w.start,w.end));
        if(missing.length===(updated.words||[]).length)throw Error('Bulunan süreler satır aralığına uymuyor; mevcut bağlantılar korundu.');
        change(d=>({...d,segment:updated,passages:[...d.passages,...passagePool(updated).filter(p=>!d.passages.some(q=>q.start===p.start&&q.end===p.end&&q.label===p.label)).map(p=>({...p,id:'text-aligned:'+p.id}))]}));
        setNotice(`Yazdığın sözler korundu. ${updated.words!.length-missing.length} kelimeye süre bağlandı. ${missing.length?`Ses bekleyen: ${missing.map(w=>w.word).join(', ')}. `:''}Dinleyerek kontrol et, ardından “Uygula ve kaydet”e bas.`);
        return;
      }
      const wordClips=Array.isArray(data.word_times)?passagePool(bindDetectedWords(target,data.word_times)).map(p=>({...p,id:'text-aligned:'+p.id})):[];
      change(d=>({...d,passages:[...d.passages,...clips.filter(p=>!d.passages.some(q=>q.id===p.id)),...wordClips.filter(p=>![...d.passages,...clips].some(q=>q.start===p.start&&q.end===p.end&&q.label===p.label))]}));
      setNotice(data.message+(data.skipped?.length?` ${data.skipped.length} bölüm için güvenli sınır bulunamadı.`:''));
    }catch(e){if(!controller.signal.aborted)setError((e as Error).message);}
    finally{if(!controller.signal.aborted)setDetecting(false);}
  };
  const findWords=async()=>{
    if(!validRange(rangeStart,rangeEnd)||rangeEnd-rangeStart>60){setError('En fazla 60 saniyelik geçerli bir aralık seçin.');return;}
    const controller=new AbortController();detection.current=controller;
    const version=revision.current;setFinding(true);setCandidates([]);setError('');
    try{
      const response=await fetch('/api/lyrics/deep-words',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file_name:file,start:rangeStart,end:rangeEnd}),signal:controller.signal});
      const created=await response.json();if(!response.ok)throw Error(typeof created.detail==='string'?created.detail:'Çözümleme başlatılamadı.');
      const deadline=Date.now()+10*60*1000;
      while(!controller.signal.aborted){
        if(Date.now()>deadline)throw Error('Çözümleme uzun sürdü. Mevcut düzenleme korundu.');
        await new Promise(resolve=>setTimeout(resolve,1500));
        const status=await fetch(`/status/${encodeURIComponent(created.task_id)}`,{signal:controller.signal});
        if(!status.ok)throw Error('Çözümleme durumu alınamadı.');
        const task=await status.json();setNotice(task.message || 'Ses karşılaştırılıyor…');
        if(task.status==='failed')throw Error(task.error || 'Çözümleme tamamlanamadı.');
        if(task.status==='completed'){
          if(version!==revision.current)throw Error('Bu sırada düzenleme yapıldı; yeni sözlerin korundu. Tekrar çözümle.');
          candidateRevision.current=version;setCandidates(task.result.candidates);setNotice(task.result.message);
          if(!task.result.candidates?.length&&draft.segment.text.trim())await detect(true);
          break;
        }
      }
    }catch(e){if(!controller.signal.aborted)setError((e as Error).message);}
    finally{if(!controller.signal.aborted)setFinding(false);}
  };
  const listen=async(start:number,end:number)=>{
    const request=++sequence.current;setError('');
    try {const started=await player.current?.play(`/output/${encodeURIComponent(file)}`,start,end,()=>{if(request===sequence.current)setPlaying(false);});
      if(request===sequence.current)setPlaying(!!started);
    } catch(e){if(request===sequence.current){setPlaying(false);setError((e as Error).message);}}
  };
  const select=(id:string)=>{const p=draft.passages.find(p=>p.id===id);if(p){setSelected(id);setRangeStart(p.start);setRangeEnd(p.end);setCursor((p.start+p.end)/2);setSplitTarget((draft.segment.words||[]).findIndex(w=>Math.abs(w.start-p.start)<1e-7&&Math.abs(w.end-p.end)<1e-7));setFirstWord('');setSecondWord('');}};
  const save=()=>{
    try {
      if(!draft.segment.text.trim()) throw Error('Satır boş olamaz.');
      if(draft.passages.some(p=>duration && p.end>duration)) throw Error('Ses dosyasını aşan bir parça var.');
      onApply(draft.segment);
      try {projectStorage.setItem(poolKey(file,row,draft.segment.start,draft.segment.id),JSON.stringify(draft.passages));}catch{}
    }catch(e){setError((e as Error).message);}
  };
  const button='rounded-lg border border-white/15 px-3 py-2 text-sm hover:bg-white/10 disabled:opacity-40';
  return <div className="fixed inset-0 z-[100] bg-black/80 flex items-center justify-center p-4" onClick={e=>e.stopPropagation()}>
    <section role="dialog" aria-modal="true" aria-label="Ses parçalarını sözlere bağla" className="w-full max-w-[1440px] max-h-[95dvh] overflow-y-auto rounded-2xl border border-white/15 bg-[#1b1823] p-5 sm:p-8 text-slate-200 space-y-6">
      <div className="flex flex-wrap justify-between items-center gap-3"><h3 className="text-xl font-semibold">Ses parçalarını sözlere bağla · Satır {row+1}</h3><div className="flex flex-wrap gap-2"><button className="rounded-lg bg-amber-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40" disabled={finding||detecting||!draft.passages.length} onClick={()=>change(bindAllPassages)}>Tüm ses parçalarını bağla</button><button className={button} onClick={onClose}>Vazgeç</button></div></div>
      <p className="text-xs text-amber-200/80">Toplu bağlama bu satırdaki mevcut sözleri korur; ses parçalarını zaman sırasıyla eşleştirir. Sonucu dinleyip “Uygula ve kaydet” ile kaydedebilirsin.</p>
      <p className="text-sm text-slate-400">Bir ses parçasını dinle, sonra kelimenin üzerine sürükle. Dokunmatik kullanımda parçayı seçip kelimeye bas. Değişiklikler “Uygula ve kaydet” ile kaydedilir.</p>
      <label className="block text-sm">Satırın tamamını düzenle<input className="mt-2 w-full rounded-lg bg-[#292433] border border-white/20 p-3" value={draft.segment.text} onChange={e=>updateLyricInput(e.currentTarget,text=>change(d=>editPassageText(d,text)))}/></label>
      <div className="flex flex-wrap items-center gap-3">
        <button className={button} disabled={detecting||finding||!draft.segment.text.trim()} onClick={()=>void detect(true)}>{detecting?'Ses analiz ediliyor…':'Yazdığım sözleri sesle hizala'}</button>
        <p className="text-xs text-slate-400">Yukarıdaki metni değiştirmeden satırın ses aralığında kelime sürelerini arar. Elle bağladığın kelimeler korunur; bulunan süreleri dinleyerek kontrol et.</p>
      </div>
      <div className="rounded-xl bg-[#292433] p-3">
        <svg viewBox="0 0 800 100" className="w-full h-24" role="img" aria-label="Satırın ses dalgası">
          {peaks.map((v,i)=><line key={i} x1={i*2} x2={i*2} y1={50-Math.min(1,v)*48} y2={50+Math.min(1,v)*48} stroke="#34d399"/>)}
          <line x1={(cursor-left)/(right-left)*800} x2={(cursor-left)/(right-left)*800} y1="0" y2="100" stroke="#fbbf24"/>
        </svg>
        <label className="text-xs">Bölme noktası: {cursor.toFixed(3)} sn<input aria-label="Bölme noktası" type="range" className="w-full" min={left} max={Math.min(right,duration||right)} step="0.001" value={cursor} onChange={e=>setCursor(Number(e.target.value))}/></label>
      </div>
      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-xs">Başlangıç<input aria-label="Parça başlangıcı" className="block bg-[#292433] rounded p-2 w-28" type="number" min="0" step="0.001" value={rangeStart} onChange={e=>setRangeStart(Number(e.target.value))}/></label>
        <label className="text-xs">Bitiş<input aria-label="Parça bitişi" className="block bg-[#292433] rounded p-2 w-28" type="number" min="0" step="0.001" value={rangeEnd} onChange={e=>setRangeEnd(Number(e.target.value))}/></label>
        <button className={button} onClick={()=>void listen(rangeStart,rangeEnd)}>Aralığı dinle</button>
        <button className={button} disabled={finding||detecting} onClick={()=>void findWords()}>{finding?'Sözler ayrıntılı aranıyor…':'Sözleri sesten bul · 4 deneme'}</button>
        {playing&&<button className={button} onClick={()=>{sequence.current++;player.current?.stop();setPlaying(false);}}>Durdur</button>}
        <button className={button} onClick={()=>change(d=>{if(!validRange(rangeStart,rangeEnd)||(duration&&rangeEnd>duration))throw Error('Geçerli bir ses aralığı girin.');return {...d,passages:[...d.passages,{id:crypto.randomUUID(),start:rangeStart,end:rangeEnd,label:'Yeni parça'}]};})}>Aralıktan parça ekle</button>
        <button className={button} disabled={!selected} onClick={()=>change(d=>splitPassage(d,selected,cursor))}>Seçili parçayı böl</button>
        <button className={button} disabled={!selected} onClick={()=>change(d=>mergePassages(d,selected))}>Sonrakiyle birleştir</button>
      </div>
      {selectedClip&&<div className="space-y-3 rounded-xl border border-amber-400/25 bg-amber-400/5 p-4">
        <h4 className="font-semibold">Bitişik sözü iki kelimeye ayır</h4>
        <p className="text-sm text-slate-400">Seçili ses: {selectedClip.label}. Bölme noktasını dinleyerek ayarla; örneğin BİLE ve CAYABİLİRİM yaz. Seçtiğin tek kelimenin yerine bu iki kelime ve süreleri uygulanır.</p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs">Değiştirilecek kelime<StudioSelect aria-label="İkiye ayrılacak kelime" className="block rounded bg-[#292433] p-2" value={splitTarget} onValueChange={value=>setSplitTarget(Number(value))}><option value={-1}>Kelime seç</option>{draft.segment.text.trim().split(/\s+/).filter(Boolean).map((word,i)=><option key={i} value={i}>{i+1}. {word}</option>)}</StudioSelect></label>
          <label className="text-xs">İlk kelime<input aria-label="Bölünen ilk kelime" className="block w-40 rounded bg-[#292433] p-2" placeholder="BİLE" value={firstWord} onChange={e=>setFirstWord(e.target.value)}/></label>
          <label className="text-xs">İkinci kelime<input aria-label="Bölünen ikinci kelime" className="block w-40 rounded bg-[#292433] p-2" placeholder="CAYABİLİRİM" value={secondWord} onChange={e=>setSecondWord(e.target.value)}/></label>
          <label className="text-xs">Bölme noktası (sn)<input aria-label="İki kelime arasındaki bölme saniyesi" type="number" min={selectedClip.start} max={selectedClip.end} step="0.001" className="block w-32 rounded bg-[#292433] p-2" value={cursor} onChange={e=>setCursor(Number(e.target.value))}/></label>
          <button className={button} disabled={!validRange(selectedClip.start,cursor)||cursor>=selectedClip.end} onClick={()=>void listen(selectedClip.start,cursor)}>İlk kısmı dinle</button>
          <button className={button} disabled={!validRange(cursor,selectedClip.end)||cursor<=selectedClip.start} onClick={()=>void listen(cursor,selectedClip.end)}>İkinci kısmı dinle</button>
          <button className={button} disabled={finding||detecting||splitTarget<0||!firstWord.trim()||!secondWord.trim()} onClick={()=>change(d=>splitAndBindPassage(d,selected,cursor,splitTarget,firstWord,secondWord))}>İkiye böl ve kelimelere bağla</button>
        </div>
        <p className="text-xs text-slate-400">Bölme noktası başlangıçta parçanın ortasıdır; gerçek kelime geçişine göre ayarla. Geri al kullanılabilir; sonuç “Uygula ve kaydet” ile kaydedilir.</p>
      </div>}
      <div><h4 className="text-sm font-semibold mb-2">Ses parçaları · zaman sırasıyla</h4><div className="flex flex-wrap gap-2">
        <button className={button} disabled={detecting||finding} onClick={()=>void detect()}>{detecting?'Ses analiz ediliyor…':'Heceleri otomatik bul (Türkçe)'}</button>
        {[...draft.passages].sort((a,b)=>a.start-b.start).map(p=><div key={p.id} draggable onDragStart={e=>{e.dataTransfer.setData('application/x-uvr-passage',p.id);select(p.id);}} className={`rounded-lg border p-2 ${selected===p.id?'border-amber-400 bg-amber-400/10':'border-white/20'}`}>
          <button className="text-left text-sm" onClick={()=>select(p.id)}>{p.label}<span className="block text-xs text-slate-400">{p.start.toFixed(3)}–{p.end.toFixed(3)}</span></button>
          <button aria-label={`${p.label} parçasını dinle`} className="ml-3" onClick={()=>void listen(p.start,p.end)}>▶</button>
          {p.needs_review&&<span className="block text-xs text-amber-300">Hece önerisi · dinleyerek kontrol et</span>}
        </div>)}
      </div></div>
      <div><h4 className="text-sm font-semibold mb-2">Kelimeler · parçayı buraya bırak</h4><div className="flex flex-wrap gap-2">
        {(draft.segment.words||[]).map((w,i)=><div key={i} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();const id=e.dataTransfer.getData('application/x-uvr-passage');change(d=>bindPassage(d,id,i));}} className="rounded-xl border border-amber-400/30 p-3">
          <button onClick={()=>change(d=>bindPassage(d,selected,i))} className="block font-bold">{w.word}</button>
          <span className="block text-xs text-slate-400">{validRange(w.start,w.end)?`${w.start.toFixed(3)}–${w.end.toFixed(3)}`:'Ses bekliyor'}</span>
          {validRange(w.start,w.end)&&<div className="flex gap-2 mt-2 text-xs"><button onClick={()=>void listen(w.start,w.end)}>Dinle</button><button onClick={()=>change(d=>({...d,segment:{...d.segment,words:d.segment.words?.map((x,j)=>j===i?{...x,end:x.start,timing_source:'estimated',needs_review:true}:x)}}))}>Bağlantıyı kaldır</button></div>}
          {!validRange(w.start,w.end)&&<button className="mt-2 text-xs text-amber-200" disabled={finding||detecting} onClick={()=>change(d=>{
            if(!validRange(rangeStart,rangeEnd)||(duration&&rangeEnd>duration))throw Error('Önce kelimenin başlangıç ve bitişini seçip aralığı dinleyin.');
            const clip={id:crypto.randomUUID(),start:rangeStart,end:rangeEnd,label:w.word,needs_review:true};
            return bindPassage({...d,passages:[...d.passages,clip]},clip.id,i);
          })}>Seçili aralığı bu kelimeye bağla</button>}
        </div>)}
      </div></div>
      <p className="text-xs text-slate-400">Parçayı bölmek mevcut kelime bağlantısını değiştirmez. Yeni parçaları bağlamak için gerekirse eski bağlantıyı kaldır. Sessiz boşluklar birleştirilmez.</p>
      {error&&<p role="alert" className="text-sm text-rose-300">{error}</p>}
      {error&&onFit&&<div className="space-y-2 rounded-xl border border-amber-400/25 p-3">
        <button className={button} disabled={finding||detecting} onClick={()=>change(d=>{
          const fitted=onFit(d.segment);
          setNotice('Taşan ses bağlantıları komşu satır sınırından kesildi. Diğer satırlar değişmedi. İşaretli kelimeleri Dinle ile kontrol edip Uygula ve kaydet’e basın. Geri al kullanılabilir.');
          return {...d,segment:fitted,passages:[...d.passages,...passagePool(fitted).map(p=>({...p,id:'boundary:'+p.id}))]};
        })}>Taşan bağlantıları bu satıra sığdır</button>
        <p className="text-xs text-slate-400">Yalnızca bu satırdaki kelimelerin taşan başlangıç/bitişleri kesilir; ses kaydırılmaz ve komşu satırların süreleri değişmez.</p>
      </div>}
      {notice&&<p role="status" className="text-sm text-emerald-300">{notice}</p>}
      {candidates.length>0&&<div className="space-y-2 rounded-xl border border-white/15 p-3"><p className="text-sm">Seçilen ses aralığı için alternatifler. Birini seçmek bu satırın tamamını değiştirir; Geri al kullanılabilir.</p>{candidates.map((c,i)=><div key={i} className="rounded-lg bg-[#292433] p-3"><p className="text-xs text-slate-400">{c.label} · Diğer denemelerle metin benzerliği: %{Math.round(c.agreement*100)} (doğruluk oranı değildir)</p><label className="mt-3 block text-xs text-slate-300">Bulunan sözleri düzenle<textarea aria-label={`${i+1}. alternatifin sözlerini düzenle`} value={c.text} onChange={e=>setCandidates(list=>list.map((item,j)=>j===i?{...item,text:e.target.value.toLocaleUpperCase('tr-TR')}:item))} className="mt-2 block w-full min-h-24 rounded-xl border border-white/15 bg-[#14121c] p-3 text-sm text-white" /></label><p className="my-2 text-xs text-slate-400">Düzeltilen kelimeler ses aralıklarına sırayla bağlanır. Kelime ekleyip silersen eşleşme sırasını kontrol et; fazladan kelimeler ses bekler.</p><button className={button} onClick={()=>change(d=>{
        if(candidateRevision.current!==revision.current)throw Error('Bu sonuçtan sonra düzenleme yapıldı. Sözleri yeniden çözümleyin.');
        if(!c.words.length||c.words.some((w,j)=>!validRange(w.start,w.end)||(j>0&&w.start<c.words[j-1].end)))throw Error('Bu alternatifte zaman çakışması var; diğer sonucu kontrol edin.');
        const words=correctedCandidateWords(c.text,c.words); if(!words.length)throw Error('En az bir kelime yazın.'); const updated={...d.segment,text:words.map(w=>w.word).join(' '),words,start:c.words[0].start,end:c.words.at(-1)!.end};
        return {segment:updated,passages:[...d.passages,...passagePool({...updated,words:c.words}).map(p=>({...p,id:'recognized:'+p.id,needs_review:true}))]};
      })}>Düzelttiğim sözlere süreleri sırayla uygula</button></div>)}</div>}
      <div className="flex justify-between"><button className={button} disabled={!history.length} onClick={()=>{revision.current++;player.current?.stop();sequence.current++;setPlaying(false);setDraft(history.at(-1)!);setHistory(h=>h.slice(0,-1));setError('');}}>Geri al</button><button className="rounded-lg px-4 py-2 bg-amber-400 font-bold text-slate-950" onClick={save}>Uygula ve kaydet</button></div>
    </section>
  </div>;
}
