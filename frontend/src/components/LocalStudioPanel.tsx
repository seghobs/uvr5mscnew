'use client';
import React,{useEffect,useState,useRef} from 'react';
import { Activity, HardDrive, ChevronDown, RotateCcw, Square, Trash2, CheckCircle2, Clock3, Download, Inbox, Loader2 } from 'lucide-react';
import {api} from '@/lib/api';
import {backendFetch} from '@/lib/backend-fetch';
import {flushProjects,flushAllProjects} from '@/lib/project-storage';
import type {AudioJob} from '@/lib/audio-jobs';
const labels:Record<string,string>={queued:'Sırada',processing:'Çalışıyor',cancelling:'Durduruluyor',cancelled:'İptal edildi',completed:'Tamamlandı',failed:'Hata',interrupted:'Yarıda kaldı'};
export function LocalStudioPanel(){
 const refreshing=useRef(false), stoppingRef=useRef(false);
 const [stopping,setStopping]=useState(false);
 const [restarting,setRestarting]=useState(false);
 const [open,setOpen]=useState(false),[jobs,setJobs]=useState<AudioJob[]>([]),[other,setOther]=useState<any[]>([]);
 const [cache,setCache]=useState({bytes:0,files:0,limit_bytes:0}),[save,setSave]=useState({pending:0,error:''}),[error,setError]=useState('');
 const refresh=async()=>{if(refreshing.current||stoppingRef.current)return;refreshing.current=true;try{
  const [jr,cr]=await Promise.all([backendFetch('/api/audio/jobs'),backendFetch('/api/audio/cache')]);
  if(!jr.ok||!cr.ok)throw Error('İşlem durumuna ulaşılamadı.');
  const data=await jr.json();setError(previous=>['İşlem durumuna ulaşılamadı.','Sunucu bağlantısı geçici olarak kesildi; yeniden deneniyor.'].includes(previous)?'':previous);setJobs(data.jobs);setOther(data.other_jobs||[]);setCache(await cr.json());
 }catch{setError('Sunucu bağlantısı geçici olarak kesildi; yeniden deneniyor.');}finally{refreshing.current=false;}};
 useEffect(()=>{void refresh();const timer=setInterval(()=>void refresh(),3000);const listener=(e:Event)=>setSave((e as CustomEvent).detail);window.addEventListener('uvr-project-status',listener);return()=>{clearInterval(timer);window.removeEventListener('uvr-project-status',listener);};},[]);
 const action=async(url:string,method:string)=>{setError('');try{const r=await fetch(url,{method});if(!r.ok)throw Error('İşlem yapılamadı.');await refresh();}catch(e){setError((e as Error).message);}};
 const restart=async()=>{if(restarting)return;setRestarting(true);setError('');try{await flushAllProjects();const response=await fetch('/api/service/restart',{method:'POST'});if(!response.ok){const data=await response.json();throw Error(data.detail||'Yeniden başlatılamadı.');}const previous=(await response.json()).previous_pid;setError('Sunucu yeniden başlatılıyor…');for(let i=0;i<90;i++){await new Promise(r=>setTimeout(r,1000));try{const health=await fetch('/api/service');if(health.ok&&(await health.json()).pid!==previous){setError('');await refresh();return;}}catch{}}throw Error('Sunucu başlatılamadı; başlatıcıdaki hata kaydını kontrol edin.');}catch(e){setError((e as Error).message);}finally{setRestarting(false);}};
 const stopAll=async()=>{
  if(stoppingRef.current||!window.confirm('Çalışan ve bekleyen tüm işlemler sonlandırılsın mı? Tamamlanmamış işlem ilerlemesi kaybolur. Kayıtlı sözler, şarkılar ve ses dosyaları korunur.'))return;
  stoppingRef.current=true;setStopping(true);setError('');
  try{
   await flushAllProjects();
   await api.cancelAllTasks();
   setJobs([]);setOther([]);
  }catch(e){setError((e as Error).message);}
  finally{stoppingRef.current=false;setStopping(false);void refresh();}
 };
 const waiting=jobs.filter(j=>['queued','processing','cancelling'].includes(j.status)).reverse();
 const recent=jobs.filter(j=>!['queued','processing','cancelling'].includes(j.status)).slice(0,10);
 const active=waiting.length+other.filter(j=>['queued','processing','cancelling'].includes(j.status)).length;
 const buttonStyle='inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.035] px-3 py-2 text-sm font-medium text-slate-200 transition-colors hover:border-violet-300/30 hover:bg-violet-300/10 disabled:cursor-not-allowed disabled:opacity-40';
 const cachePercent=cache.limit_bytes?Math.min(100,cache.bytes/cache.limit_bytes*100):0;
 return <section className="glass-panel overflow-hidden rounded-2xl text-sm">
  <button onClick={()=>setOpen(!open)} aria-expanded={open} aria-controls="local-studio-details" className="flex w-full flex-wrap items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-white/[0.025] sm:px-5">
   <span className="flex items-center gap-3">
    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-300/10 text-violet-300"><Activity size={19}/></span>
    <span><span className="block font-semibold text-slate-100">Yerel çalışma merkezi</span><span className="mt-0.5 block text-xs text-slate-400">{active?`${active} işlem devam ediyor`:'Çalışma alanın hazır'}</span></span>
   </span>
   <span className="flex items-center gap-3 pl-[52px] sm:pl-0">
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${save.error?'border-rose-300/15 bg-rose-300/5 text-rose-300':save.pending?'border-indigo-300/15 bg-indigo-300/5 text-indigo-200':'border-emerald-300/15 bg-emerald-300/5 text-emerald-300'}`}>
     {save.error||save.pending?<Clock3 size={13}/>:<CheckCircle2 size={13}/>}{save.error?'Kayıt bekliyor':save.pending?`${save.pending} kayıt bekliyor`:'Projeler diskte'}
    </span>
    <ChevronDown size={17} className={`text-slate-400 transition-transform ${open?'rotate-180':''}`}/>
   </span>
  </button>
  {(error||save.error)&&<div role="alert" className="mx-4 mb-4 rounded-xl border border-rose-300/15 bg-rose-300/5 px-4 py-3 text-rose-200">{error||save.error} <button className="ml-2 underline underline-offset-4" onClick={()=>{setError('');void flushProjects().then(()=>refresh()).catch(e=>setError(e.message));}}>Tekrar dene</button></div>}
  {open&&<div id="local-studio-details" className="space-y-4 border-t border-white/[0.07] p-4 sm:p-5">
   <div className="flex flex-wrap gap-2">
    <button className={buttonStyle} disabled={restarting||stopping} onClick={()=>void restart()}>{restarting?<Loader2 size={15} className="animate-spin"/>:<RotateCcw size={15}/>} {restarting?'Yeniden başlatılıyor…':'Sunucuyu yeniden başlat'}</button>
    <button className={`${buttonStyle} text-rose-200 enabled:hover:border-rose-300/30 enabled:hover:bg-rose-300/10`} disabled={!active||stopping||restarting} onClick={()=>void stopAll()}>{stopping?<Loader2 size={15} className="animate-spin"/>:<Square size={14}/>} {stopping?'İşlemler durduruluyor…':'Tüm işlemleri sonlandır'}</button>
   </div>
   <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/[0.07] bg-black/10 p-4">
    <div className="min-w-0 flex-1 basis-52">
     <div className="flex items-center gap-2 font-medium text-slate-200"><HardDrive size={16} className="text-violet-300"/>Ton önbelleği <span className="ml-auto text-xs font-normal text-slate-400">{cache.files} dosya</span></div>
     <div className="my-2.5 h-1.5 overflow-hidden rounded-full bg-white/[0.06]" role="progressbar" aria-label="Ton önbelleği kullanımı" aria-valuenow={Math.round(cachePercent)} aria-valuemin={0} aria-valuemax={100}><div className="h-full rounded-full bg-violet-400/70 transition-all" style={{width:`${cachePercent}%`}}/></div>
     <p className="text-xs tabular-nums text-slate-400">{(cache.bytes/1024**2).toFixed(1)} MB / {(cache.limit_bytes/1024**3).toFixed(0)} GB kullanılıyor</p>
    </div>
    <button className={buttonStyle} onClick={()=>void action('/api/audio/cache','DELETE')}><Trash2 size={15} className="text-slate-400"/>Önbelleği ve geçmişi temizle</button>
   </div>
   <div className="space-y-2">
    <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400"><Clock3 size={14}/>İşlem geçmişi</h4>
    {!jobs.length&&!other.length&&<div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-white/10 px-4 py-6 text-center"><Inbox size={24} className="text-slate-500"/><p className="font-medium text-slate-300">Henüz bir işlem yok</p><p className="text-xs text-slate-400">Ses işlemlerin ve durumları burada görünecek.</p></div>}
    {[...waiting,...recent].map(j=><div key={j.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-black/10 p-3"><div className="min-w-0 flex-1"><p className="break-words font-medium text-slate-200">{j.file_name}</p><p className="mt-1 text-xs text-slate-400">{j.pitch>0?'+':''}{j.pitch} yarım ton{j.kind==='export'?' · Dışa aktarım':''} · {labels[j.status]||j.status}</p><p className="mt-1 break-words text-xs text-slate-400">{j.message}</p></div><div className="flex flex-wrap gap-2">{['queued','processing'].includes(j.status)&&<button className={buttonStyle} onClick={()=>void action(`/api/audio/jobs/${j.id}`,'DELETE')}>İptal et</button>}{['failed','cancelled','interrupted'].includes(j.status)&&<button className={buttonStyle} onClick={()=>void action(`/api/audio/jobs/${j.id}/retry`,'POST')}><RotateCcw size={14}/>Yeniden başlat</button>}{j.output_file&&<a className={buttonStyle} href={`/output/${encodeURIComponent(j.output_file)}`} download><Download size={14}/>İndir</a>}</div></div>)}
    {other.filter(j=>['queued','processing','cancelling'].includes(j.status)).map(j=><div key={j.id} className="rounded-xl border border-violet-300/10 bg-violet-300/5 p-3"><p className="font-medium text-slate-200">{j.model_type==='supplied_alignment'?'Söz senkronu':j.model_type||'Diğer işlem'}</p><p className="mt-1 break-words text-xs text-slate-400">{labels[j.status]||j.status} · {j.message||j.id}</p></div>)}
   </div>
  </div>}
 </section>;
}
