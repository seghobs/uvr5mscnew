'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import {Play,Pause,RotateCcw,RotateCw,Volume2,VolumeX,Maximize,Minimize,Clapperboard} from 'lucide-react';
import type {LyricSegment} from '@/lib/types';
import {velocityLevels} from '@/lib/karaoke-spectrum';
import {videoSegments,wordFillWithNeighbors,soloWindows,rowMotion,rowPose,isInstrumentalText} from '@/lib/karaoke-timing';

export function KaraokeVideoPreview({file,segments,theme,aspectRatio,header,onPlay}:{onPlay:()=>void;file:string;segments:LyricSegment[];theme:string;aspectRatio:string;header:string}) {
  const canvas=useRef<HTMLCanvasElement>(null),audio=useRef<HTMLAudioElement>(null);
  const [error,setError]=useState('');
  const [loadFailed,setLoadFailed]=useState(false);
  const restorePosition=useRef<number|null>(null);
  const reloadAudio=()=>{
    const media=audio.current;if(!media)return;
    restorePosition.current=Number.isFinite(media.currentTime)?media.currentTime:position;
    setError('');setLoadFailed(false);setPlaying(false);media.load();
  };
  const audioFailed=(media:HTMLAudioElement)=>{
    const code=media.error?.code;
    if(code===1)return;
    setPlaying(false);setLoadFailed(true);
    setError(code===3?'Tarayıcı sesi çözemedi. Ses dosyasını yeniden yükleyin.':code===4?'Ses kaynağı açılamadı veya biçimi desteklenmiyor. Yeniden yüklemeyi deneyin.':'Ses bağlantısı kesildi. Kaldığınız süreyi koruyarak yeniden yükleyebilirsiniz.');
  };
  const backdrop=useRef<HTMLImageElement|null>(null);
  useEffect(()=>{const image=new Image();let active=true;image.onload=()=>{if(active)backdrop.current=image;};image.src=`/api/karaoke/background?v=4&theme=${encodeURIComponent(theme)}&vertical=${aspectRatio==='9:16'}`;return()=>{active=false;};},[theme,aspectRatio]);
  const shell=useRef<HTMLElement>(null);
  const [playing,setPlaying]=useState(false),[position,setPosition]=useState(0),[duration,setDuration]=useState(0),[volume,setVolume]=useState(1),[fullscreen,setFullscreen]=useState(false);
  const clock=(t:number)=>`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`;
  const seek=(time:number)=>{if(audio.current){audio.current.currentTime=Math.max(0,Math.min(duration,time));setPosition(audio.current.currentTime);}};
  const toggle=()=>{const media=audio.current;if(!media)return;if(!media.paused)media.pause();else{setError('');void context.current?.resume();void media.play().catch(()=>setError('Oynatma başlatılamadı. Tekrar deneyin.'));}};
  const changeVolume=(value:number)=>{setVolume(value);if(audio.current)audio.current.volume=value;};
  useEffect(()=>{const update=()=>setFullscreen(document.fullscreenElement===shell.current);document.addEventListener('fullscreenchange',update);return()=>document.removeEventListener('fullscreenchange',update);},[]);
  const toggleFullscreen=async()=>{try{if(document.fullscreenElement===shell.current)await document.exitFullscreen();else await shell.current?.requestFullscreen();}catch{setError('Bu tarayıcı tam ekranı açamadı.');}};
  const schedule=useMemo(()=>{
    const source=videoSegments(segments).filter(s=>s.text.trim()).slice().sort((a,b)=>a.start-b.start);
    return source.map((row,i)=>({row,motion:rowMotion(row,i===source.length-1,source[i+1]?.start)}));
  },[segments]);
  const solos=useMemo(()=>soloWindows(videoSegments(segments),duration),[segments,duration]);
  const analyser=useRef<AnalyserNode|null>(null),context=useRef<AudioContext|null>(null);
  const cleanupTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  useEffect(()=>{
    const media=audio.current;if(!media)return;
    if(cleanupTimer.current)clearTimeout(cleanupTimer.current);
    if(!context.current){
      const ctx=new AudioContext();context.current=ctx;
      const source=ctx.createMediaElementSource(media),meter=ctx.createAnalyser();meter.fftSize=2048;meter.smoothingTimeConstant=.35;
      source.connect(meter);meter.connect(ctx.destination);analyser.current=meter;
    }
    return ()=>{media.pause();cleanupTimer.current=setTimeout(()=>{void context.current?.close();context.current=null;analyser.current=null;},0);};
  },[file]);
  useEffect(()=>{
    let frame=0;
    let meterData=new Float32Array(1024);
    const layouts=new Map<LyricSegment,{pieces:string[];widths:number[];wordWidths:number[];total:number;colored:HTMLCanvasElement;mask:HTMLCanvasElement;output:HTMLCanvasElement}>();
    const draw=()=>{
      const el=canvas.current,c=el?.getContext('2d');if(!el||!c)return;
      const vertical=aspectRatio==='9:16',width=vertical?1080:1920,height=vertical?1920:1080;
      if(el.width!==width||el.height!==height){el.width=width;el.height=height;}
      const palette:Record<string,[string,string]>={gold:['#070A12','#ffd700'],neon:['#060914','#00ffff'],cyberpunk:['#090514','#ef46d9'],emerald:['#040D0A','#34d399']};
      const [bg,color]=palette[theme]||palette.gold;
      c.fillStyle=bg;c.fillRect(0,0,width,height);if(backdrop.current)c.drawImage(backdrop.current,0,0,width,height);
      const time=audio.current?.currentTime||0;
      const text=(value:string,y:number,size:number,fill:string,bold=true)=>{
        c.font=`${bold?'bold ':''}${size}px Segoe UI`;c.textAlign='center';c.textBaseline='bottom';c.lineWidth=1;c.strokeStyle='#000';c.fillStyle=fill;
        c.strokeText(value,width/2,y,width-120);c.fillText(value,width/2,y,width-120);
      };
      if(header){c.font='bold 32px Segoe UI';c.textAlign='left';c.textBaseline='top';c.fillStyle='white';c.fillText(header,110,85,width-220);}
      c.save();c.shadowBlur=16;c.shadowColor=color;
      const meter=analyser.current;
      if(meter){
        if(meterData.length!==meter.frequencyBinCount)meterData=new Float32Array(meter.frequencyBinCount);
        meter.getFloatFrequencyData(meterData);
        const levels=velocityLevels(meterData,meter.context.sampleRate,meter.fftSize);
        const w=vertical?840:1600,x=(width-w)/2,bottom=vertical?1832:984,maxHeight=vertical?112:80;
        const bars=80,step=w/bars;
        for(let i=0;i<bars;i++){
          const h=Math.max(2,maxHeight*levels[i]);c.fillStyle=color;c.fillRect(x+i*step,bottom-h,step-4,h);
        }
      }
      c.restore();
      const total=audio.current?.duration||0;
      if(Number.isFinite(total)&&total>0){
        const fraction=Math.max(0,Math.min(1,time/total)),right=width-390;
        c.save();c.strokeStyle=color;c.lineWidth=6;c.lineCap='round';
        if(fraction>0){c.beginPath();c.moveTo(110,205);c.lineTo(110+(right-110)*fraction,205);c.stroke();}
        const remaining=Math.ceil(Math.max(0,total-time));
        c.font='20px Segoe UI';c.textAlign='left';c.textBaseline='middle';c.fillStyle='#c4c8cd';
        c.fillText(`${Math.floor(remaining/60).toString().padStart(2,'0')}:${(remaining%60).toString().padStart(2,'0')} KALDI`,right+24,205);c.restore();
      }
      for(let i=0;i<14;i++){const elapsed=time-i*.65;if(elapsed<0)continue;const phase=(elapsed%12)/12;const x=i%2===0?24+(i*13)%32:width-24-(i*13)%32;c.fillStyle='rgba(187,204,221,'+(.43*Math.min(1,phase*6,(1-phase)*6))+')';c.fillRect(x+phase*12,(height-70)+(170-height+70)*phase,3,3);}
      const visible=schedule.map(s=>({...s,pose:rowPose(s.row,s.motion,time)})).filter(s=>s.pose!==null);
      const upcoming=schedule.find((s,i)=>s.motion.enter>time&&(i===0||schedule[i-1].row.start<=time));
      const baseline=vertical?1010:550,size=vertical?70:76,distance=vertical?180:160;
      for(const active of visible){
        const pose=active.pose!;const y=baseline+pose.offset*distance;
        c.save();c.globalAlpha=pose.opacity;
        if(time<active.row.start){
          if(!isInstrumentalText(active.row.text)){
            c.save();c.globalAlpha=Math.max(0,1-(time-active.motion.enter)/.24);
            text(active.row.text,baseline-distance,size*.4,'#95959c',false);c.restore();
          }
          text(active.row.text,y,size*pose.scale,'#b4b9c6');c.restore();continue;
        }
        const row=active.row;const words=row.words||[];
        if(!words.length)text(row.text,y,size,'white');
        if(words.length){
          c.font=`bold ${size}px Segoe UI`;
          c.textBaseline='bottom';
          let layout=layouts.get(row);
          if(!layout){
            const pieces=words.map((w,i)=>w.word+(i<words.length-1?' ':'')),widths=pieces.map(p=>c.measureText(p).width),total=widths.reduce((a,b)=>a+b,0);
            const make=()=>{const layer=document.createElement('canvas');layer.width=Math.ceil(total)+2;layer.height=size+20;return layer;};
            const colored=make(),mask=make(),output=make(),ink=colored.getContext('2d')!;
            const palettes:Record<string,[string,string]>={gold:['#c97700','#fff6a3'],neon:['#008db9','#b7fbff'],cyberpunk:['#931a98','#ffc1f2'],emerald:['#00804b','#b4ffd3']};
            const [dark,light]=palettes[theme]||palettes.gold;
            ink.font=c.font;ink.textBaseline='bottom';const metrics=ink.measureText(pieces.join(''));
            const gradient=ink.createLinearGradient(0,size+10-metrics.actualBoundingBoxAscent,0,size+10+metrics.actualBoundingBoxDescent);gradient.addColorStop(0,light);gradient.addColorStop(1,dark);
            ink.fillStyle=gradient;ink.fillText(pieces.join(''),0,size+10);
            layout={pieces,widths,wordWidths:words.map(w=>c.measureText(w.word).width),total,colored,mask,output};layouts.set(row,layout);
          }
          const {pieces,widths,total,wordWidths,colored,mask,output}=layout;
          const alpha=mask.getContext('2d')!,ink=output.getContext('2d')!;alpha.clearRect(0,0,mask.width,mask.height);
          let x=0;
          words.forEach((word,i)=>{
            const fraction=wordFillWithNeighbors(word,time,words[i-1],words[i+1]);
            if(fraction>0){
              const wordWidth=wordWidths[i],feather=Math.min(48/Math.max(wordWidth,1),.35)*2*Math.min(fraction,1-fraction);
              const sweep=alpha.createLinearGradient(x,0,x+wordWidth,0);
              sweep.addColorStop(0,'white');sweep.addColorStop(Math.max(0,fraction-feather/2),'white');
              sweep.addColorStop(Math.min(1,fraction+feather/2),fraction>=1?'white':'transparent');sweep.addColorStop(1,fraction>=1?'white':'transparent');
              alpha.fillStyle=sweep;alpha.fillRect(x,0,wordWidth,mask.height);
            }
            x+=widths[i];
          });
          ink.clearRect(0,0,output.width,output.height);ink.drawImage(colored,0,0);ink.globalCompositeOperation='destination-in';ink.drawImage(mask,0,0);ink.globalCompositeOperation='source-over';
          c.save();c.translate(width/2,y);c.scale(Math.min(1,(width-120)/total)*pose.scale,pose.scale);c.translate(-total/2,0);c.textAlign='left';
          x=0;pieces.forEach((piece,i)=>{c.fillStyle='#b4b9c6';c.strokeText(piece,x,0);c.fillText(piece,x,0);x+=widths[i];});
          c.drawImage(output,0,-size-10);c.restore();
        }
        c.restore();
      }
      if(!visible.length&&solos.some(([start,end])=>time>=start&&time<end))text('Solo...',baseline,44,'#d0c4ed',false);
      if(upcoming&&!isInstrumentalText(upcoming.row.text)){
        const upper=baseline-distance; text(upcoming.row.text,upper,size*.4,'#95959c',false);
        const remaining=upcoming.row.start-time;
        if(remaining<=3){
          c.save();c.globalAlpha=Math.min(1,(upcoming.motion.enter-time)/.15);
          text(`${Math.ceil(remaining)} sn · HAZIRLAN`,upper+48,18,'#b4b9c6',false);
          c.fillStyle=color;c.fillRect(width/2-70,upper+62,140*Math.max(0,1-remaining/3),3);c.restore();
        }
      }
      frame=requestAnimationFrame(draw);
    };draw();return ()=>cancelAnimationFrame(frame);
  },[schedule,solos,theme,aspectRatio,header]);
  const iconButton='flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-zinc-300 transition-colors hover:bg-white/10 hover:text-white disabled:opacity-30';
  return <section ref={shell} className="overflow-hidden rounded-3xl border border-white/10 bg-[#17141f] shadow-xl fullscreen:flex fullscreen:flex-col fullscreen:justify-center">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] px-5 py-4 sm:px-6">
      <div className="flex items-center gap-3"><span className="rounded-xl bg-indigo-400/10 p-2.5 text-indigo-300"><Clapperboard size={20}/></span><div><h4 className="text-base font-semibold text-white">Stüdyo önizlemesi</h4><p className="mt-0.5 text-xs text-zinc-400">İzle, kontrol et, sonra oluştur.</p></div></div>
      <div className="flex items-center gap-2 text-xs text-zinc-400"><span className={`h-1.5 w-1.5 rounded-full ${playing?'bg-emerald-300':'bg-zinc-500'}`} />{playing?'Oynatılıyor':'Hazır'}<span className="ml-2 rounded-lg border border-white/10 px-2.5 py-1 font-mono">{aspectRatio}</span></div>
    </div>
    <div className="flex items-center justify-center bg-[radial-gradient(ellipse_at_top,_#292235,_#100e16)] p-3 sm:p-6">
      <canvas ref={canvas} aria-label="Karaoke video önizlemesi" className="block rounded-xl shadow-[0_16px_60px_#0008] ring-1 ring-white/5" style={{width:`min(100%, calc(${fullscreen?'70':'56'}vh * ${aspectRatio==='9:16'?'9 / 16':'16 / 9'}))`,aspectRatio:aspectRatio==='9:16'?'9 / 16':'16 / 9'}} />
    </div>
    <div className="space-y-3 border-t border-white/[0.06] px-5 py-4 sm:px-6">
      <input type="range" aria-label="Önizleme zaman çizelgesi" min={0} max={duration||1} step={0.01} value={position} disabled={!duration} onChange={e=>seek(Number(e.target.value))} className="block h-1.5 w-full cursor-pointer appearance-none rounded-full accent-violet-300" style={{background:`linear-gradient(to right,#b7a1f5 ${duration?position/duration*100:0}%,#ffffff14 ${duration?position/duration*100:0}%)`}} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1 sm:gap-2">
          <button className={iconButton} title="5 saniye geri" aria-label="Önizlemeyi 5 saniye geri sar" disabled={!duration} onClick={()=>seek(position-5)}><RotateCcw size={18}/></button>
          <button className="flex h-11 w-11 items-center justify-center rounded-2xl bg-violet-300 text-slate-950 shadow-lg shadow-violet-400/10 transition hover:bg-violet-200 disabled:opacity-40" disabled={!duration} aria-label={playing?'Önizlemeyi duraklat':'Önizlemeyi oynat'} onClick={toggle}>{playing?<Pause size={20} fill="currentColor"/>:<Play size={20} fill="currentColor" className="ml-0.5"/>}</button>
          <button className={iconButton} title="5 saniye ileri" aria-label="Önizlemeyi 5 saniye ileri sar" disabled={!duration} onClick={()=>seek(position+5)}><RotateCw size={18}/></button>
          <span className="ml-2 font-mono text-xs tabular-nums text-zinc-400"><span className="text-zinc-100">{clock(position)}</span> / {clock(duration)}</span>
        </div>
        <div className="flex items-center gap-2"><button className={iconButton} aria-label={volume?'Önizleme sesini kapat':'Önizleme sesini aç'} onClick={()=>changeVolume(volume?0:1)}>{volume?<Volume2 size={18}/>:<VolumeX size={18}/>}</button><input aria-label="Önizleme ses seviyesi" type="range" min={0} max={1} step={0.01} value={volume} onChange={e=>changeVolume(Number(e.target.value))} className="w-20 accent-violet-300 sm:w-24"/><span className="mx-2 h-5 w-px bg-white/10"/><button className={iconButton} aria-label={fullscreen?'Tam ekrandan çık':'Önizlemeyi tam ekran aç'} onClick={()=>void toggleFullscreen()}>{fullscreen?<Minimize size={18}/>:<Maximize size={18}/>}</button></div>
      </div>
      <p className="text-[11px] leading-relaxed text-zinc-500">Tam şarkı · Son videoda yazı çizimi ve ses görseli küçük farklılıklar gösterebilir.</p>
      {error&&<p role="alert" className="text-sm text-rose-300">{error}</p>}
      {loadFailed&&<button onClick={reloadAudio} className="rounded-xl border border-violet-300/30 bg-violet-300/10 px-4 py-2 text-sm text-violet-200 hover:bg-violet-300/20">Sesi yeniden yükle</button>}
    </div>
    <audio key={file} ref={audio} preload="metadata" src={`/output/${encodeURIComponent(file)}`} className="hidden" onLoadedMetadata={e=>{
      const media=e.currentTarget,total=Number.isFinite(media.duration)?media.duration:0;
      setDuration(total);setError('');setLoadFailed(false);
      if(restorePosition.current!==null&&total>0){media.currentTime=Math.min(restorePosition.current,total);setPosition(media.currentTime);restorePosition.current=null;}
    }} onCanPlay={()=>{setLoadFailed(false);setError('');}} onTimeUpdate={e=>{if(restorePosition.current===null)setPosition(e.currentTarget.currentTime);}} onPause={()=>setPlaying(false)} onEnded={()=>setPlaying(false)} onPlay={()=>{setError('');setLoadFailed(false);setPlaying(true);onPlay();void context.current?.resume().catch(()=>setError('Önizleme sesi başlatılamadı.'));}} onError={e=>audioFailed(e.currentTarget)} />
  </section>;
}
