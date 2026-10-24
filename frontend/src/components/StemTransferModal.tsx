'use client';
import React,{useEffect,useRef,useState,useMemo} from 'react';
import {ArrowRightLeft,Play,Square,Undo2,X,Repeat2} from 'lucide-react';
import {StudioSelect} from './StudioSelect';

function previewGains(mode:string,amount:number):number[]{
  return [mode.startsWith('vocal')?1:0,mode.startsWith('inst')?1:0,mode.endsWith('after')?(mode.startsWith('vocal')?-amount:amount):0];
}

export type StemPair={vocal:string;instrumental:string};
export function StemTransferModal({vocal,instrumentals,initialTime,onClose,onApply}:{vocal:string;instrumentals:string[];initialTime:number;onClose:()=>void;onApply:(before:StemPair,after:StemPair,time:number)=>void}) {
  const expected=vocal.replace(/vocals?|vox/i,'instrumental').toLowerCase();
  const [pair,setPair]=useState<StemPair>({vocal,instrumental:instrumentals.find(x=>x.toLowerCase()===expected)||''});
  const [history,setHistory]=useState<StemPair[]>([]);
  const [start,setStart]=useState(Math.max(0,initialTime));
  const [end,setEnd]=useState(Math.max(0,initialTime)+2);
  const [amount,setAmount]=useState(1);
  const [frequencyMode,setFrequencyMode]=useState(false);
  const [low,setLow]=useState(300);
  const [high,setHigh]=useState(4000);
  const [scope,setScope]=useState<'selected'|'all'>('selected');
  const [mode,setMode]=useState('vocal_before');
  const [loop,setLoop]=useState(true);
  const previewSettings=useRef({mode,amount,loop});
  previewSettings.current={mode,amount,loop};
  const [duration,setDuration]=useState(0);
  const [peaks,setPeaks]=useState<number[]>([]);
  const [view,setView]=useState<[number,number]|null>(null);
  const [loading,setLoading]=useState(true);
  const [saving,setSaving]=useState(false);
  const [playing,setPlaying]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const context=useRef<AudioContext|null>(null);
  const buffers=useRef<AudioBuffer[]>([]);
  const sources=useRef<AudioBufferSourceNode[]>([]);
  const gains=useRef<GainNode[]>([]);
  const filters=useRef<BiquadFilterNode[]>([]);
  const bandGains=useRef<GainNode[]>([]);
  const envelope=useRef<GainNode|null>(null);
  const envelopeTimer=useRef<ReturnType<typeof setInterval>|null>(null);
  const filterSettings=useRef({frequencyMode,low,high});filterSettings.current={frequencyMode,low,high};
  const revision=useRef(0);
  const drag=useRef<number|null>(null);
  const stop=()=>{revision.current++;if(envelopeTimer.current)clearInterval(envelopeTimer.current);envelopeTimer.current=null;for(const node of filters.current)node.disconnect();filters.current=[];for(const node of bandGains.current)node.disconnect();bandGains.current=[];envelope.current?.disconnect();envelope.current=null;for(const node of sources.current){node.onended=null;node.stop();node.disconnect();}sources.current=[];for(const gain of gains.current)gain.disconnect();gains.current=[];setPlaying(false);};
  useEffect(()=>{
    const ctx=new AudioContext();context.current=ctx;
    return()=>{if(envelopeTimer.current)clearInterval(envelopeTimer.current);revision.current++;for(const node of sources.current){node.onended=null;node.stop();node.disconnect();}for(const gain of gains.current)gain.disconnect();void ctx.close();};
  },[]);
  useEffect(()=>{
    let live=true;const controller=new AbortController();stop();setLoading(true);setError('');
    buffers.current=[];
    if(!pair.instrumental){setLoading(false);return()=>controller.abort();}
    Promise.all([pair.vocal,pair.instrumental].map(async name=>{
      const response=await fetch('/output/'+encodeURIComponent(name),{signal:controller.signal});
      if(!response.ok)throw Error('Ses dosyası yüklenemedi');
      return context.current!.decodeAudioData(await response.arrayBuffer());
    })).then(values=>{
      if(!live)return;
      if(values[0].length!==values[1].length||values[0].numberOfChannels!==values[1].numberOfChannels)throw Error('Aynı süre ve kanal sayısına sahip ayrıştırma çifti seçin.');
      buffers.current=values;const d=values[0].duration;setDuration(d);setStart(s=>Math.min(s,Math.max(0,d-.01)));setEnd(e=>Math.min(e,d));

    }).catch(e=>{if(live&&!controller.signal.aborted)setError(e.message);}).finally(()=>{if(live)setLoading(false);});
    return()=>{live=false;controller.abort();};
  },[pair]);
  useEffect(()=>{
    const buffer=buffers.current[0];if(loading||!buffer)return;
    const channel=buffer.getChannelData(0),left=view?.[0]??0,right=view?.[1]??buffer.duration;
    const first=Math.floor(left*buffer.sampleRate),last=Math.min(channel.length,Math.ceil(right*buffer.sampleRate)),result=[];
    for(let n=0;n<1000;n++){let p=0;for(let j=first+Math.floor(n*(last-first)/1000);j<first+Math.floor((n+1)*(last-first)/1000);j++)p=Math.max(p,Math.abs(channel[j]));result.push(p);}
    setPeaks(result);
  },[view,loading,duration]);
  const valid=!loading&&buffers.current.length===2&&start>=0&&end>start&&end<=duration;
  const preview=async()=>{
    stop();if(!valid)return;
    if(frequencyMode&&(end-start>30||end-start<.05)){setError('Hafif canlı frekans önizlemesi için 0,05–30 saniyelik bir döngü seç. Kaydetme sırasında seçime veya tüm şarkıya uygulayabilirsin.');return;}
    const version=revision.current;
    const ctx=context.current!;setError('');
    try{await ctx.resume();}catch{setError('Ses çıkışı başlatılamadı. Tekrar dinlemeyi deneyin.');return;}
    if(version!==revision.current)return;
    const [v,i]=buffers.current;const first=Math.round(start*v.sampleRate),last=Math.round(end*v.sampleRate);
    if(last<=first)return;
    if((last-first)/v.sampleRate<.05){setError('Döngü önizlemesi için en az 50 ms seçin.');return;}
    const clips=[0,1,2].map(()=>ctx.createBuffer(v.numberOfChannels,last-first,v.sampleRate));
    const fade=Math.min(Math.round(v.sampleRate*.005),Math.floor((last-first)/2));
    for(let c=0;c<v.numberOfChannels;c++){
      clips[0].copyToChannel(v.getChannelData(c).subarray(first,last),c);
      clips[1].copyToChannel(i.getChannelData(c).subarray(first,last),c);
      clips[2].copyToChannel(v.getChannelData(c).subarray(first,last),c);
    }
    const initial=previewGains(previewSettings.current.mode,previewSettings.current.amount);
    const nodes=clips.map((clip,index)=>{
      const node=ctx.createBufferSource(),gain=ctx.createGain();
      node.buffer=clip;node.loop=previewSettings.current.loop;gain.gain.value=initial[index];
      if(index===2){
        const hp=ctx.createBiquadFilter(),lp=ctx.createBiquadFilter(),dry=ctx.createGain(),wet=ctx.createGain(),edge=ctx.createGain();
        hp.type='highpass';lp.type='lowpass';// Web Audio highpass/lowpass Q is in dB; match the export Butterworth Q.
        hp.Q.value=lp.Q.value=20*Math.log10(Math.SQRT1_2);
        hp.frequency.value=filterSettings.current.low;lp.frequency.value=filterSettings.current.high;
        dry.gain.value=filterSettings.current.frequencyMode?0:1;wet.gain.value=filterSettings.current.frequencyMode?1:0;
        node.connect(dry);dry.connect(edge);node.connect(hp);hp.connect(lp);lp.connect(wet);wet.connect(edge);edge.connect(gain);
        filters.current=[hp,lp];bandGains.current=[dry,wet];envelope.current=edge;
      }else node.connect(gain);
      gain.connect(ctx.destination);gains.current.push(gain);return node;
    });
    sources.current=nodes;
    nodes[0].onended=()=>{if(sources.current[0]===nodes[0])stop();};
    // A single audio clock keeps A/B, the destination and transfer phase-aligned.
    const when=ctx.currentTime+.02;
    const period=clips[0].duration,fadeSeconds=fade/v.sampleRate;
    let nextEdge=when;
    const scheduleEdges=()=>{
      const gain=envelope.current?.gain;if(!gain)return;
      if(nextEdge+period<ctx.currentTime)nextEdge=when+Math.floor((ctx.currentTime-when)/period)*period;
      while(nextEdge<ctx.currentTime+.75){
        gain.setValueAtTime(0,nextEdge);
        gain.linearRampToValueAtTime(1,nextEdge+fadeSeconds);
        gain.setValueAtTime(1,nextEdge+period-fadeSeconds);
        gain.linearRampToValueAtTime(0,nextEdge+period);
        nextEdge+=period;
      }
    };
    scheduleEdges();envelopeTimer.current=setInterval(scheduleEdges,100);
    for(const node of nodes)node.start(when);
    setPlaying(true);
  };
  useEffect(()=>{
    const ctx=context.current;if(!ctx)return;
    const values=previewGains(mode,amount);
    gains.current.forEach((gain,index)=>{
      gain.gain.cancelScheduledValues(ctx.currentTime);
      gain.gain.setTargetAtTime(values[index],ctx.currentTime,.005);
    });
  },[mode,amount]);
  useEffect(()=>{for(const node of sources.current)node.loop=loop;},[loop]);

  useEffect(()=>{
    const ctx=context.current;if(!ctx)return;
    filters.current.forEach((filter,index)=>{
      filter.frequency.cancelScheduledValues(ctx.currentTime);
      filter.frequency.setTargetAtTime(index===0?low:high,ctx.currentTime,.01);
    });
    bandGains.current.forEach((gain,index)=>{
      gain.gain.cancelScheduledValues(ctx.currentTime);
      gain.gain.setTargetAtTime((index===0?!frequencyMode:frequencyMode)?1:0,ctx.currentTime,.005);
    });
  },[low,high,frequencyMode]);

  const save=async()=>{
    if(!valid)return;stop();setSaving(true);setError('');
    try{
      const response=await fetch('/api/audio/transfer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...pair,start,end,amount,scope,...(frequencyMode?{frequency_low:low,frequency_high:high}:{})})});
      const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'Aktarım kaydedilemedi');
      const next={vocal:result.vocal,instrumental:result.instrumental};
      onApply(pair,next,start);setHistory(h=>[...h,pair]);setPair(next);
      setNotice(`${scope==='all'?'Tüm şarkı · ':''}${frequencyMode?`${low}–${high} Hz · `:''}${result.start.toFixed(3)}–${result.end.toFixed(3)} sn aktarıldı. İki kanal aynı konumda ve sürede kaydedildi.`);
    }catch(e){setError((e as Error).message);}finally{setSaving(false);}
  };
  const left=view?.[0]??0,right=view?.[1]??duration;
  const point=(event:React.PointerEvent<SVGSVGElement>)=>{const rect=event.currentTarget.getBoundingClientRect();return Math.max(left,Math.min(right,left+(event.clientX-rect.left)/rect.width*(right-left)));};
  const waveform=useMemo(()=>(<div className="rounded-2xl border border-white/10 bg-[#17141f] p-4">
        <svg viewBox="0 0 1000 140" className="h-36 w-full touch-none cursor-crosshair" role="img" aria-label="Aktarılacak ses aralığını sürükleyerek seç" onPointerDown={e=>{if(saving||!duration)return;stop();drag.current=point(e);e.currentTarget.setPointerCapture(e.pointerId);setStart(drag.current);setEnd(drag.current);}} onPointerMove={e=>{if(drag.current===null)return;const p=point(e);setStart(Math.min(drag.current,p));setEnd(Math.max(drag.current,p));}} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}}>
          {peaks.map((p,n)=>{const x=(n+.5)/peaks.length*1000;return <line key={n} x1={x} x2={x} y1={70-Math.min(1,p)*65} y2={70+Math.min(1,p)*65} stroke="#a78bda" strokeWidth="2"/>;})}
          <rect x={Math.max(0,(start-left)/(right-left||1)*1000)} width={Math.max(0,(Math.min(end,right)-Math.max(start,left))/(right-left||1)*1000)} y="0" height="140" fill="#b7a1f5" fillOpacity=".2" stroke="#d8caff"/>
        </svg>
        <div className="flex justify-between text-xs text-slate-400"><span>{left.toFixed(3)} sn</span><span>{right.toFixed(3)} sn</span></div>
      </div>),[peaks,start,end,left,right,saving,duration]);
  const button='inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[.04] px-4 py-2.5 text-sm text-slate-200 hover:bg-indigo-300/10 disabled:opacity-40';
  return <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm" onClick={e=>e.stopPropagation()}>
    <section role="dialog" aria-modal="true" aria-label="Vokalden enstrümana aktar" className="custom-scrollbar max-h-[94dvh] w-full max-w-5xl space-y-5 overflow-y-auto rounded-3xl border border-white/15 bg-[#211d2a] p-6 text-slate-200 shadow-2xl">
      <header className="flex items-center justify-between gap-4"><h3 className="flex items-center gap-2 text-lg font-bold"><ArrowRightLeft className="text-indigo-300" size={20}/>Vokalden enstrümana aktar</h3><button aria-label="Aktarım penceresini kapat" className={button} disabled={saving} onClick={()=>{stop();onClose();}}><X size={18}/></button></header>
      <p className="text-sm text-slate-400">Dalga üzerinde sürükleyerek aralık seç. Seçilen ses vokalden çıkarılır ve enstrümana aynı saniyelerde eklenir. Kanal süreleri değişmez. Frekans filtresiyle yalnızca hedeflediğin ses bölgesini aktarabilirsin; aynı frekanstaki insan sesi de etkilenebilir.</p>
      <label className="block space-y-2 text-xs text-slate-400">Hedef enstrüman kanalı<StudioSelect aria-label="Aktarım hedefi" value={pair.instrumental} disabled={saving||history.length>0} onValueChange={value=>setPair({...pair,instrumental:value})} className="w-full rounded-xl border border-white/10 bg-black/20 p-3 text-sm"><option value="">Aynı ayrıştırmanın enstrümanını seç</option>{[...new Set([pair.instrumental,...instrumentals])].filter(Boolean).map(name=><option key={name} value={name}>{name}</option>)}</StudioSelect></label>
      {loading?<p className="text-sm text-indigo-200">Sesler hazırlanıyor…</p>:<>
      {waveform}
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs">Başlangıç (sn)<input aria-label="Aktarım başlangıcı" type="number" min="0" max={duration} step=".001" value={start} disabled={saving} onChange={e=>{stop();setStart(Number(e.target.value));}} className="mt-2 block w-32 rounded-xl border border-white/10 bg-black/20 p-3"/></label>
        <label className="text-xs">Bitiş (sn)<input aria-label="Aktarım bitişi" type="number" min="0" max={duration} step=".001" value={end} disabled={saving} onChange={e=>{stop();setEnd(Number(e.target.value));}} className="mt-2 block w-32 rounded-xl border border-white/10 bg-black/20 p-3"/></label>
        <button className={button} disabled={!valid} onClick={()=>setView([Math.max(0,start-2),Math.min(duration,end+2)])}>Seçime yakınlaş</button><button className={button} onClick={()=>setView(null)}>Tüm şarkı</button>
      </div>
      <div className="space-y-4 rounded-2xl border border-indigo-300/20 bg-indigo-300/[.04] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3"><h4 className="font-semibold">Frekans seçerek aktarım</h4><button type="button" aria-pressed={frequencyMode} disabled={saving} className={button+(frequencyMode?' bg-indigo-300/20 text-indigo-100':'')} onClick={()=>setFrequencyMode(value=>!value)}>{frequencyMode?'Frekans filtresi açık':'Tüm frekanslar'}</button></div>
        <p className="text-xs text-slate-400">Canlı önizleme yalnızca seçtiğin kısa döngüyü işler. GPU / UVR çalıştırılmaz; kaydırıcılar dosyayı yeniden render etmez.</p>
        {frequencyMode&&<>
          <svg viewBox="0 0 800 60" role="img" aria-label={`Aktarım frekans bandı ${low}–${high} Hz`} className="h-16 w-full rounded-lg bg-black/20"><line x1="0" x2="800" y1="50" y2="50" stroke="#62566f"/><rect x={Math.log(low/20)/Math.log(1000)*800} width={Math.log(high/low)/Math.log(1000)*800} y="8" height="42" rx="5" fill="#b7a1f5" opacity=".35"/>{[20,100,1000,10000,20000].map(hz=><text key={hz} x={Math.max(14,Math.min(780,Math.log(hz/20)/Math.log(1000)*800))} y="59" textAnchor="middle" fill="#a99bb9" fontSize="10">{hz>=1000?hz/1000+'k':hz}</text>)}</svg>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-xs">Alt frekans · {low} Hz<input aria-label="Alt frekans" disabled={saving} type="range" min="0" max="1000" step="1" value={Math.log(low/20)/Math.log(1000)*1000} onChange={e=>setLow(Math.min(high-1,Math.round(20*Math.pow(1000,Number(e.target.value)/1000))))} className="my-3 w-full accent-[#b7a1f5]"/><input aria-label="Alt frekans Hz" disabled={saving} type="number" min="20" max={high-1} value={low} onChange={e=>setLow(Math.max(20,Math.min(high-1,Number(e.target.value)||20)))} className="w-full rounded-xl border border-white/10 bg-black/20 p-2"/></label>
            <label className="text-xs">Üst frekans · {high} Hz<input aria-label="Üst frekans" disabled={saving} type="range" min="0" max="1000" step="1" value={Math.log(high/20)/Math.log(1000)*1000} onChange={e=>setHigh(Math.max(low+1,Math.round(20*Math.pow(1000,Number(e.target.value)/1000))))} className="my-3 w-full accent-[#b7a1f5]"/><input aria-label="Üst frekans Hz" disabled={saving} type="number" min={low+1} max="20000" value={high} onChange={e=>setHigh(Math.min(20000,Math.max(low+1,Number(e.target.value)||low+1)))} className="w-full rounded-xl border border-white/10 bg-black/20 p-2"/></label>
          </div><p className="text-xs text-slate-400">Yumuşak geçişli 12 dB/oktav filtreler. Frekans sınırları keskin bir duvar değildir. Anlık değişiklikleri “Sonra” seçiliyken duyarsın.</p>
        </>}
      </div>
      <label className="block text-sm">Aktarım miktarı: %{Math.round(amount*100)}<input aria-label="Aktarım miktarı" type="range" min=".01" max="1" step=".01" value={amount} disabled={saving} onChange={e=>setAmount(Number(e.target.value))} className="mt-3 w-full accent-[#b7a1f5]"/></label>
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label="Dinlenecek kanal" className="flex gap-1 rounded-xl border border-white/10 p-1">{[['vocal','Vokal'],['inst','Enstrüman']].map(([channel,label])=><button key={channel} type="button" aria-pressed={mode.startsWith(channel)} className={button+(mode.startsWith(channel)?' bg-indigo-300/20 text-indigo-100':'')} onClick={()=>setMode(channel+'_'+mode.split('_')[1])}>{label}</button>)}</div>
        <div role="group" aria-label="Önce ve sonra karşılaştır" className="flex gap-1 rounded-xl border border-white/10 p-1">{[['before','Önce'],['after','Sonra']].map(([version,label])=><button key={version} type="button" aria-pressed={mode.endsWith(version)} className={button+(mode.endsWith(version)?' bg-indigo-300/20 text-indigo-100':'')} onClick={()=>setMode(mode.split('_')[0]+'_'+version)}>{label}</button>)}</div>
        <button type="button" aria-pressed={loop} className={button+(loop?' bg-indigo-300/20 text-indigo-100':'')} onClick={()=>setLoop(value=>!value)}><Repeat2 size={16}/>Döngü {loop?'açık':'kapalı'}</button>
        <button className={button} disabled={!valid||saving} onClick={()=>playing?stop():void preview().catch(e=>{stop();setError('Önizleme oynatılamadı: '+(e as Error).message);})}>{playing?<><Square size={16}/>Durdur</>:<><Play size={16}/>Seçimi dinle</>}</button>
      </div>
      <p className="text-xs text-slate-400">{playing?'Seçim çalıyor. ':''}Miktar ve Önce / Sonra geçişleri çalma konumunu değiştirmeden uygulanır. Miktarın etkisini “Sonra” seçiliyken duyarsın.</p>
      {!frequencyMode&&mode==='vocal_after'&&amount===1&&<p className="text-xs text-indigo-200">%100 aktarımda seçili bölüm vokalden tamamen çıkarılır; bu önizlemede sessizlik beklenir. Sesi duymak için “Vokal · Önce” veya “Enstrüman · Sonra” seç.</p>}
      </>}
      {error&&<p role="alert" className="rounded-xl border border-rose-300/20 bg-rose-300/5 p-3 text-sm text-rose-200">{error}</p>}
      {notice&&<p role="status" className="text-sm text-indigo-200">{notice}</p>}
      <div role="group" aria-label="Aktarımı uygulama alanı" className="flex flex-wrap gap-2 rounded-xl border border-white/10 p-2">{[['selected','Yalnız seçilen aralığa uygula'],['all','Tüm şarkıya uygula']].map(([value,label])=><button key={value} type="button" disabled={saving} aria-pressed={scope===value} className={button+(scope===value?' bg-indigo-300/20 text-indigo-100':'')} onClick={()=>setScope(value as 'selected'|'all')}>{label}</button>)}</div>
      {scope==='all'&&<p className="text-xs text-indigo-200">Önizleme kısa seçimin üzerinde kalır; kaydettiğinde aynı frekans ve miktar ayarı şarkının tamamına uygulanır.</p>}
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4"><button className={button} disabled={!history.length||saving} onClick={()=>{stop();const previous=history[history.length-1];onApply(pair,previous,start);setPair(previous);setHistory(h=>h.slice(0,-1));setNotice('Son aktarım geri alındı. Önceki iki kanal geri yüklendi.');}}><Undo2 size={16}/>Son aktarımı geri al</button><button className="rounded-xl bg-indigo-300 px-5 py-3 text-sm font-bold text-slate-950 hover:bg-indigo-200 disabled:opacity-40" disabled={!valid||saving} onClick={()=>void save()}>{saving?'Kanallar kaydediliyor…':scope==='all'?'Tüm şarkıya uygula ve kaydet':'Seçime uygula ve kaydet'}</button></footer>
      <p className="text-xs text-slate-400">Orijinal dosyalar korunur. Yeni WAV çifti çalışma alanına kaydedilir. Geri alma bu pencere açıkken kullanılabilir.</p>
    </section>
  </div>;
}
