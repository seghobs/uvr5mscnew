'use client';

import { useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { LyricSegment } from '@/lib/types';
import { uppercaseLyric } from '@/lib/karaoke-timing';

type Candidate = { id: number; artist: string; title: string; album: string; duration: number; text: string; source: string; url: string };
type Row = { index: number; original: string; proposed: string; changed: boolean; reason: string; similarity: number };

export default function LyricsReferenceModal({ sourceFile, duration, segments, onClose, onApply }: {
  sourceFile: string; duration: number; segments: LyricSegment[]; onClose: () => void;
  onApply: (snapshot: LyricSegment[], edits: Record<number, string>) => Promise<void>;
}) {
  const [snapshot] = useState(() => structuredClone(segments));
  const [url, setUrl] = useState('');
  const [artist, setArtist] = useState('');
  const [title, setTitle] = useState('');
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [reference, setReference] = useState('');
  const [rows, setRows] = useState<Row[]>([]);
  const [selected, setSelected] = useState<Record<number, boolean>>({});
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [source, setSource] = useState('');
  const field = 'w-full rounded-lg border border-white/15 bg-slate-950 p-2 text-sm text-white';
  const button = 'rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white disabled:opacity-40';
  const run = async (label: string, work: () => Promise<void>) => {
    setBusy(label); setMessage('');
    try { await work(); } catch (e) { setMessage(e instanceof Error ? e.message : 'İşlem tamamlanamadı.'); }
    finally { setBusy(''); }
  };
  const compare = async (text: string) => {
    const data = await api.referenceRequest('compare', { segments: snapshot, reference: text });
    setRows(data.rows); setSelected({});
  };
  const search = async (youtube: string, performer: string, track: string) => {
    setRows([]); setCandidates([]); setReference(''); setSource('');
    const data = await api.referenceRequest('search', {youtube_url: youtube.trim(), artist: performer, title: track});
    const ordered = [...data.candidates].sort((a: Candidate, b: Candidate) => duration > 0 ? Math.abs(a.duration - duration) - Math.abs(b.duration - duration) : 0);
    setArtist(data.artist); setTitle(data.title); setCandidates(ordered);
    try { localStorage.setItem(`lyrics-reference:${sourceFile}`, JSON.stringify({url: youtube, artist: data.artist, title: data.title})); } catch {}
    if (!data.candidates.length) setMessage('Söz bulunamadı. Resmî kaynaktan aldığın sözleri aşağıya yapıştırabilirsin.');
    if (ordered.length && (duration <= 0 || Math.abs(ordered[0].duration - duration) <= 2)) {
      setReference(ordered[0].text); setSource(ordered[0].url);
      await compare(ordered[0].text);
      setMessage('Süreye en yakın aday karşılaştırıldı. Aynı kayıt olduğunu ve önerilen düzeltmeleri kontrol edin.');
    } else if (ordered.length) {
      setMessage('Bulunan sözlerin süreleri bu kayıtla uyuşmuyor. Otomatik aday seçilmedi; uygun sürümü kendin seç veya referans metni yapıştır.');
    }
  };
  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    try {
      const saved = JSON.parse(localStorage.getItem(`lyrics-reference:${sourceFile}`) || 'null');
      if (saved) {
        setUrl(saved.url); setArtist(saved.artist); setTitle(saved.title);
        void run('Sözler aranıyor…', () => search(saved.url, saved.artist, saved.title));
      }
    } catch {}
  }, []);
  return <div className="fixed inset-0 z-[130] flex items-center justify-center bg-slate-950/90 p-4">
    <section role="dialog" aria-modal="true" aria-label="Sözleri bul ve doğrula" className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-white/15 bg-slate-900 p-5 space-y-4">
      <div className="flex items-center justify-between"><h3 className="text-lg font-bold text-white">Sözleri bul ve doğrula</h3><button disabled={!!busy} onClick={onClose} className={button}>Kapat</button></div>
      <p className="text-sm text-slate-300">YouTube bağlantısından şarkıyı bul veya sanatçı ve şarkı adını gir. Referans sözler LRCLIB’den ücretsiz aranır; resmî veya hatasız oldukları garanti edilmez. Ses dosyan gönderilmez.</p>
      <fieldset disabled={!!busy} className="space-y-3">
        <input aria-label="YouTube bağlantısı" placeholder="YouTube bağlantısı" value={url} onChange={e => {setUrl(e.target.value); setArtist(''); setTitle(''); setRows([]);}} className={field}/>
        <div className="grid grid-cols-2 gap-2"><input aria-label="Sanatçı" placeholder="Sanatçı" value={artist} onChange={e => setArtist(e.target.value)} className={field}/><input aria-label="Şarkı adı" placeholder="Şarkı adı" value={title} onChange={e => setTitle(e.target.value)} className={field}/></div>
        <button className={button} onClick={() => void run('Sözler aranıyor…', async () => {
          await search(url, artist, title);
        })}>Sözleri bul</button>
        <div className="space-y-2">{candidates.map(c => <button key={c.id} className="block w-full rounded-lg border border-white/15 p-2 text-left text-sm text-slate-200" onClick={() => void run('Metin karşılaştırılıyor…', async () => {
          setReference(c.text); setSource(c.url); await compare(c.text);
        })}>{c.artist} — {c.title} · {c.album} · {Math.round(c.duration)} sn · Karşılaştır</button>)}</div>
        <label className="block text-sm text-slate-300">Referans sözler — farklı sürümlere dikkat et
          <textarea aria-label="Referans sözler" className={field} rows={5} value={reference} onChange={e => {setReference(e.target.value); setRows([]); setSource('');}}/>
        </label>
        {source && <a className="text-sm text-indigo-300 underline" href={source} target="_blank" rel="noreferrer">Seçilen söz kaynağı</a>}
        <button disabled={!reference.trim()} className={button} onClick={() => void run('Metin karşılaştırılıyor…', () => compare(reference))}>Mevcut sözlerle karşılaştır</button>
      </fieldset>
      {rows.length > 0 && <div className="space-y-3">
        <p className="text-sm text-slate-300">{rows.filter(r => r.changed).length} satırda fark bulundu. Uygulanacak satırları seç; kayıttaki tekrarları koru. Metin benzerliği, ses doğruluğu değildir.</p>
        {rows.map(row => <div key={row.index} className="rounded-xl border border-white/10 p-3 space-y-2">
          <label className="flex gap-2 text-sm text-slate-300"><input type="checkbox" disabled={!!busy} checked={!!selected[row.index]} onChange={e => setSelected({...selected, [row.index]: e.target.checked})}/>Satır {row.index + 1}: {row.reason}</label>
          <p className="text-sm text-slate-400">Mevcut: {row.original}</p>
          <input aria-label={`Satır ${row.index + 1} düzeltmesi`} disabled={!!busy} className={field} value={uppercaseLyric(row.proposed)} onChange={e => {setRows(rows.map(r => r.index === row.index ? {...r, proposed: uppercaseLyric(e.target.value)} : r)); setSelected({...selected, [row.index]: true});}}/>
        </div>)}
        <button className={button} disabled={!!busy || !rows.some(r => selected[r.index] && r.proposed.trim())} onClick={() => void run('Seçilen satırlar vokalle hizalanıyor…', async () => {
          const edits = Object.fromEntries(rows.filter(r => selected[r.index]).map(r => [r.index, uppercaseLyric(r.proposed)]));
          await onApply(snapshot, edits); onClose();
        })}>Seçilenleri düzelt ve sesle hizala</button>
      </div>}
      <p role="status" className="text-sm text-amber-300">{busy || message}</p>
    </section>
  </div>;
}
