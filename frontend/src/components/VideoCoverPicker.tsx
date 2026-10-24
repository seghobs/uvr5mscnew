'use client';

import {useEffect, useRef, useState} from 'react';
import {ImagePlus, Trash2} from 'lucide-react';

export function VideoCoverPicker({value,onChange,disabled=false,onBusyChange}:{value:string;onChange:(image:string)=>void;disabled?:boolean;onBusyChange:(busy:boolean)=>void}) {
  const input=useRef<HTMLInputElement>(null);
  const request=useRef(0);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>()=>{request.current++;onBusyChange(false);},[onBusyChange]);
  async function select(file?:File) {
    if(!file)return;
    const id=++request.current;
    setError('');
    if(!['image/jpeg','image/png','image/webp'].includes(file.type)){setError('JPG, PNG veya WebP görsel seçin.');return;}
    if(file.size>10*1024*1024){setError('Görsel en fazla 10 MB olabilir.');return;}
    setBusy(true);onBusyChange(true);
    let bitmap:ImageBitmap|undefined;
    try {
      bitmap=await createImageBitmap(file);
      const scale=Math.min(1,1920/Math.max(bitmap.width,bitmap.height));
      const canvas=document.createElement('canvas');
      canvas.width=Math.max(1,Math.round(bitmap.width*scale));
      canvas.height=Math.max(1,Math.round(bitmap.height*scale));
      const context=canvas.getContext('2d');
      if(!context)throw new Error();
      context.fillStyle='#09090b';context.fillRect(0,0,canvas.width,canvas.height);
      context.drawImage(bitmap,0,0,canvas.width,canvas.height);
      if(id===request.current)onChange(canvas.toDataURL('image/jpeg',.9));
    }catch{if(id===request.current)setError('Görsel açılamadı. Başka bir dosya seçin.');}
    finally{bitmap?.close();if(id===request.current){setBusy(false);onBusyChange(false);}}
  }
  return <div className="border-t border-white/10 pt-4 flex flex-col sm:flex-row gap-4 sm:items-center">
    <div className="w-40 aspect-video shrink-0 rounded-xl border border-white/10 bg-black/40 overflow-hidden flex items-center justify-center">
      {/* A user-selected local image, also used as the MP4 poster. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {value?<img src={value} alt="Seçilen video kapağı" className="w-full h-full object-contain"/>:<ImagePlus className="w-7 h-7 text-zinc-500"/>}
    </div>
    <div className="space-y-2">
      <p className="text-xs font-bold text-zinc-200">Video kapak görseli <span className="font-normal text-zinc-400">(isteğe bağlı)</span></p>
      <p className="text-xs text-zinc-400">JPG, PNG veya WebP · En fazla 10 MB. Seçmeden de video oluşturabilirsin.</p>
      <div className="flex gap-2">
        <button type="button" disabled={busy||disabled} onClick={()=>input.current?.click()} className="flex items-center gap-2 rounded-xl border border-indigo-400/30 bg-indigo-400/10 px-3 py-2 text-xs font-bold text-indigo-300 disabled:opacity-50"><ImagePlus className="w-4 h-4"/>{busy?'Görsel hazırlanıyor…':value?'Kapağı değiştir':'Kapak görseli seç'}</button>
        {value&&<button type="button" disabled={busy||disabled} onClick={()=>{request.current++;onChange('');setError('');}} className="flex items-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-xs text-zinc-300"><Trash2 className="w-4 h-4"/>Kaldır</button>}
      </div>
      {error&&<p role="alert" className="text-xs text-rose-300">{error}</p>}
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" aria-label="Video kapak görseli seç" className="hidden" onChange={e=>{void select(e.target.files?.[0]);e.target.value='';}}/>
    </div>
  </div>;
}
