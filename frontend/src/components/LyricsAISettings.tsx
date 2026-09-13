'use client';
import {forwardRef,useEffect,useImperativeHandle,useState} from 'react';

export const LyricsAISettings=forwardRef<{save:()=>Promise<boolean>}>(function LyricsAISettings(_,ref){
  const [key,setKey]=useState(''),[enabled,setEnabled]=useState(false),[configured,setConfigured]=useState(false);
  const [ready,setReady]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
  useEffect(()=>{let active=true;fetch('/api/settings/lyrics-ai').then(async r=>{if(!r.ok)throw Error('Ayarlar okunamadı.');return r.json();}).then(s=>{if(active){setEnabled(s.enabled);setConfigured(s.configured);setReady(true);}}).catch(e=>{if(active)setMessage(e.message);});return()=>{active=false;};},[]);
  const save=async(test=false)=>{
    if(!ready||busy)return false;
    setBusy(true);setMessage('');
    try{
      const r=await fetch('/api/settings/lyrics-ai',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled,...(key.trim()?{api_key:key.trim()}:{})})});
      if(!r.ok)throw Error('Ayarlar kaydedilemedi.');
      const data=await r.json();setConfigured(data.configured);setKey('');
      if(test){const check=await fetch('/api/settings/lyrics-ai/test',{method:'POST'});if(!check.ok){const e=await check.json();throw Error(e.detail||'Bağlantı kurulamadı.');}}
      setMessage(test?'Bağlantı başarılı.':'AI ayarları kaydedildi.');
      return true;
    }catch(e){setMessage(e instanceof Error?e.message:'İşlem başarısız.');return false;}finally{setBusy(false);}
  };
  useImperativeHandle(ref,()=>({save:()=>save()}));
  return <section className="space-y-3 rounded-2xl border border-violet-400/20 bg-violet-400/5 p-4">
    <h4 className="text-sm font-bold text-violet-200">Yapay zekâ ile söz düzeltme</h4>
    <p className="text-xs text-slate-400">Gemini 3.8 Flash — Sözleri ve ilgili vokal bölümlerini Google’a gönderir. Kelime zamanları ayrıca yerelde doğrulanır.</p>
    <label className="flex items-center gap-2 text-xs text-slate-200"><input type="checkbox" checked={enabled} disabled={!ready||busy} onChange={e=>setEnabled(e.target.checked)}/>Yeni söz çözümlemelerinde tüm satırları otomatik incele</label>
    <label className="block text-xs text-slate-300">Google API anahtarı
      <input type="password" autoComplete="new-password" value={key} disabled={!ready||busy} onChange={e=>setKey(e.target.value)} placeholder={configured?'Anahtar kayıtlı · değiştirmek için yenisini yazın':'API anahtarını girin'} className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/60 p-3 text-xs"/>
    </label>
    <div className="flex gap-2"><button type="button" disabled={!ready||busy} onClick={()=>void save()} className="rounded-xl bg-violet-500/20 px-3 py-2 text-xs text-violet-200 disabled:opacity-40">AI ayarlarını kaydet</button><button type="button" disabled={!ready||busy} onClick={()=>void save(true)} className="rounded-xl border border-white/10 px-3 py-2 text-xs disabled:opacity-40">{busy?'Kontrol ediliyor…':'Kaydet ve bağlantıyı test et'}</button></div>
    {message&&<p role="status" className="text-xs text-slate-300">{message}</p>}
  </section>;
});
