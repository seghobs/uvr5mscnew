'use client';

import { useEffect, useRef, useState } from 'react';
import { Search, Loader2, Music2 } from 'lucide-react';

type Song = { source:string; id:string; title:string; artist:string; language?:string; instrumental?:boolean; lyrics_access?:string };
type Group = { source:string; status:string; error?:string; results:Song[]; pagination?:{has_next:boolean|null} };
type Results = { sources:Record<string,Group> };
const names:Record<string,string>={lyricstranslate:'LyricsTranslate',lrclib:'LRCLIB',genius:'Genius',lyricfind:'LyricFind',musixmatch:'Musixmatch'};

async function request<T>(path:string,signal:AbortSignal):Promise<T> {
  const res=await fetch(`/api/lyrics/catalog/${path}`,{signal});
  const data=await res.json();
  if(!res.ok)throw Error(typeof data.detail==='string'?data.detail:data.detail?.message||'Kaynağa ulaşılamadı. Başka bir sonuç deneyebilir veya sözleri elle yapıştırabilirsiniz.');
  return data;
}

export default function LyricsCatalogSearch({initialTitle,initialArtist,onSelect,onBusyChange,disabled}:{
  initialTitle:string;initialArtist:string;onSelect:(text:string)=>void;onBusyChange:(busy:boolean)=>void;disabled:boolean;
}) {
  const [title,setTitle]=useState(/^(instrumental|vocals|karaoke track)$/i.test(initialTitle.trim())?'':initialTitle);
  const [artist,setArtist]=useState(initialArtist==='UVR5 AI Studio'?'':initialArtist);
  const [groups,setGroups]=useState<Results['sources']|null>(null);
  const [page,setPage]=useState(0);
  const [busy,setBusy]=useState('');
  const [message,setMessage]=useState('');
  const controller=useRef<AbortController|null>(null);
  useEffect(()=>()=>controller.current?.abort(),[]);
  useEffect(()=>{onBusyChange(Boolean(busy));return()=>onBusyChange(false);},[busy,onBusyChange]);
  const run=async(label:string,work:(signal:AbortSignal)=>Promise<void>)=>{
    controller.current?.abort();const current=new AbortController();controller.current=current;
    const timeout=setTimeout(()=>current.abort(),30000);
    setBusy(label);setMessage('');
    try{await work(current.signal);}catch(error){
      if(controller.current===current)setMessage(current.signal.aborted?'Arama süresi doldu. Tekrar deneyebilir veya sözleri elle yapıştırabilirsiniz.':error instanceof Error?error.message:'Sözler alınamadı.');
    }finally{clearTimeout(timeout);if(controller.current===current)setBusy('');}
  };
  const search=(nextPage=0)=>run('search',async signal=>{
    setGroups(null);
    const data=await request<Results>(`search?${new URLSearchParams({q:title.trim(),artist:artist.trim(),page:String(nextPage)})}`,signal);
    setGroups(data.sources);setPage(nextPage);
    if(!Object.values(data.sources).some(group=>group.results.length))setMessage('Bu aramada söz bulunamadı. Aramayı değiştirebilir veya aşağıya sözleri elle yapıştırabilirsiniz.');
  });
  const choose=(song:Song)=>run(`${song.source}:${song.id}`,async signal=>{
    const data=await request<{lyrics:string|null;status:string;note?:string}>(`lyrics?${new URLSearchParams({source:song.source,id:song.id})}`,signal);
    if(!data.lyrics?.trim())throw Error('Bu kayıtta kullanılabilir söz bulunamadı. Başka bir sonuç seçebilir veya elle yapıştırabilirsiniz.');
    onSelect(data.lyrics);
    setMessage(`${names[song.source]} · ${song.artist||''} — ${song.title}: sözler aşağıya alındı. Bu kayıtla uyumunu kontrol edip senkronlamayı başlatın.${data.note?' '+data.note:''}`);
  });
  const field='w-full rounded-xl border border-white/10 bg-[#14121c]/80 p-3 text-sm text-slate-200 placeholder:text-zinc-500';
  const blocked=disabled||Boolean(busy);
  return <section className="space-y-3" aria-label="Şarkı sözü ara">
    <form className="space-y-3" onSubmit={event=>{event.preventDefault();if(!blocked&&(title.trim()||artist.trim()))void search();}}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="text-xs text-zinc-300 space-y-1 block">Şarkı adı veya söz<div><input aria-label="Şarkı adı veya söz" maxLength={128} value={title} disabled={blocked} onChange={e=>{setTitle(e.target.value);setGroups(null);setPage(0);}} placeholder="Örn. Nesrine" className={field}/></div></label>
        <label className="text-xs text-zinc-300 space-y-1 block">Sanatçı<div><input aria-label="Sanatçı" maxLength={128} value={artist} disabled={blocked} onChange={e=>{setArtist(e.target.value);setGroups(null);setPage(0);}} placeholder="Örn. Berdan Mardini" className={field}/></div></label>
      </div>
      <button type="submit" disabled={blocked||(!title.trim()&&!artist.trim())} className="flex items-center justify-center gap-2 rounded-xl bg-purple-500/20 border border-purple-400/30 px-4 py-2.5 text-sm text-purple-200 disabled:opacity-40 w-full">
        {busy==='search'?<Loader2 className="w-4 h-4 animate-spin"/>:<Search className="w-4 h-4"/>}{busy==='search'?'Kaynaklarda aranıyor…':'Kaynaklarda söz ara'}
      </button>
    </form>
    {groups&&<div className="space-y-3 max-h-64 overflow-y-auto pr-1">
      {Object.values(groups).map(group=><div key={group.source} className="rounded-xl border border-white/10 bg-white/[0.025] p-3">
        <h4 className="text-xs font-semibold text-purple-200 mb-2">{names[group.source]} · {group.results.length} sonuç</h4>
        {group.status!=='ok'?<p className="text-xs text-zinc-400">{group.status==='not_configured'?'Bu kaynak için Musixmatch API anahtarı tanımlı değil.':group.error||'Kaynağa şu anda ulaşılamıyor.'}</p>:!group.results.length?<p className="text-xs text-zinc-400">Sonuç bulunamadı.</p>:group.results.map(song=><button key={`${song.source}:${song.id}`} type="button" disabled={blocked||song.instrumental||song.lyrics_access==='authorization_required'} onClick={()=>void choose(song)} className="w-full flex items-center gap-3 text-left rounded-lg p-2 hover:bg-purple-400/10 disabled:opacity-50">
          {busy===`${song.source}:${song.id}`?<Loader2 className="w-4 h-4 shrink-0 animate-spin"/>:<Music2 className="w-4 h-4 shrink-0 text-purple-300"/>}
          <span className="min-w-0"><span className="block text-sm text-zinc-100 break-words">{song.title}</span><span className="block text-xs text-zinc-400">{song.artist||'Sanatçı belirtilmemiş'}{song.language?` · ${song.language}`:''}{song.instrumental?' · Enstrümantal':''}{song.lyrics_access==='authorization_required'?' · Söz erişimi için yetki gerekiyor':''}</span></span>
        </button>)}
      </div>)}
    </div>}
    {groups&&<div className="flex justify-between text-xs text-purple-200">
      <button type="button" disabled={blocked||page===0} className="disabled:opacity-30" onClick={()=>void search(page-1)}>Önceki sonuçlar</button>
      <span>Sayfa {page+1}</span>
      <button type="button" disabled={blocked||!Object.values(groups).some(g=>g.pagination?.has_next===true||(g.pagination?.has_next===null&&g.results.length>0))} className="disabled:opacity-30" onClick={()=>void search(page+1)}>Sonraki sonuçlar</button>
    </div>}
    {message&&<p role="status" className="text-xs text-purple-200 leading-relaxed">{message}</p>}
  </section>;
}
