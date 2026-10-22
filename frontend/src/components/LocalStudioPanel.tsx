'use client';
import React,{useEffect,useState,useRef} from 'react';
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
   const result=await api.cancelAllTasks();
   for(let i=0;i<90;i++){
    await new Promise(resolve=>setTimeout(resolve,1000));
    try{const response=await backendFetch('/api/service');if(response.ok&&(await response.json()).pid!==result.previous_pid){setJobs([]);setOther([]);return;}}catch{}
   }
   throw Error('Sonlandırma gönderildi; sunucunun yeniden başlaması doğrulanamadı. Başlatıcı kaydını kontrol edin.');
  }catch(e){setError((e as Error).message);}
  finally{stoppingRef.current=false;setStopping(false);void refresh();}
 };
 const waiting=jobs.filter(j=>['queued','processing','cancelling'].includes(j.status)).reverse();
 const recent=jobs.filter(j=>!['queued','processing','cancelling'].includes(j.status)).slice(0,10);
 const active=waiting.length+other.filter(j=>['queued','processing','cancelling'].includes(j.status)).length;
 return <section className="rounded-2xl border border-violet-300/15 bg-white/[0.025] p-4 text-sm">
  <button onClick={()=>setOpen(!open)} className="w-full flex justify-between text-slate-200"><span>Yerel çalışma merkezi · {active} ses işlemi</span><span>{save.error?'Kayıt bekliyor':save.pending?`${save.pending} kayıt bekliyor`:'Projeler diskte'} · {open?'Kapat':'Göster'}</span></button>
  {(error||save.error)&&<p role="alert" className="mt-2 text-rose-300">{error||save.error} <button className="underline" onClick={()=>{setError('');void flushProjects().then(()=>refresh()).catch(e=>setError(e.message));}}>Tekrar dene</button></p>}
  {open&&<div className="mt-4 space-y-3">
   <button className="rounded-lg border border-violet-300/25 px-3 py-2 text-violet-200" disabled={restarting||stopping} onClick={()=>void restart()}>Sunucuyu yeniden başlat</button>
   <button className="rounded-lg border border-rose-300/30 px-3 py-2 text-rose-200 disabled:opacity-50" disabled={!active||stopping||restarting} onClick={()=>void stopAll()}>{stopping?'İşlemler sonlandırılıyor, sunucu hazırlanıyor…':'Tüm işlemleri sonlandır'}</button>
   <div className="flex gap-4 items-center text-slate-400"><span>Ton önbelleği: {cache.files} dosya · {(cache.bytes/1024**2).toFixed(1)} MB / {(cache.limit_bytes/1024**3).toFixed(0)} GB</span><button className="rounded-lg border border-white/15 px-3 py-1 text-slate-200" onClick={()=>void action('/api/audio/cache','DELETE')}>Önbelleği ve geçmişi temizle</button></div>
   {!jobs.length&&!other.length&&<p className="text-slate-400">İşlem geçmişi boş.</p>}
   {[...waiting,...recent].map(j=><div key={j.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-black/15 p-3"><div className="min-w-0"><p className="break-all">{j.file_name} · {j.pitch>0?'+':''}{j.pitch} yarım ton{j.kind==='export'?' · Dışa aktarım':''}</p><p className="text-xs text-slate-400">{labels[j.status]||j.status} · {j.message}</p></div><div className="flex gap-3">{['queued','processing'].includes(j.status)&&<button onClick={()=>void action(`/api/audio/jobs/${j.id}`,'DELETE')}>İptal et</button>}{['failed','cancelled','interrupted'].includes(j.status)&&<button onClick={()=>void action(`/api/audio/jobs/${j.id}/retry`,'POST')}>Yeniden başlat</button>}{j.output_file&&<a className="text-violet-300" href={`/output/${encodeURIComponent(j.output_file)}`} download>İndir</a>}</div></div>)}
   {other.filter(j=>['queued','processing','cancelling'].includes(j.status)).map(j=><div key={j.id} className="text-slate-400">{j.model_type==='supplied_alignment'?'Söz senkronu':j.model_type||'Diğer işlem'} · {labels[j.status]||j.status} · {j.message||j.id}</div>)}
  </div>}
 </section>;
}
