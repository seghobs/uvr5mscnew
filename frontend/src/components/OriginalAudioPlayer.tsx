'use client';

import { useEffect, useRef, useState, type CSSProperties } from 'react';
import WaveSurfer from 'wavesurfer.js';
import { Music, Play, Pause, Volume2, VolumeX, Loader2 } from 'lucide-react';
import { AccentColor, Language } from '@/lib/types';
import { formatTime } from '@/lib/utils';

export function OriginalAudioPlayer({ source, lang, accentColor }: {
  source: { name: string; path: string };
  lang: Language;
  accentColor: AccentColor;
}) {
  const container = useRef<HTMLDivElement>(null);
  const player = useRef<WaveSurfer | null>(null);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [retry, setRetry] = useState(0);
  const volumeRef = useRef({ volume, muted });
  volumeRef.current = { volume, muted };
  const accent = {indigo:'183 161 245',emerald:'129 200 178',rose:'233 154 180',amber:'251 191 36',violet:'202 159 233'}[accentColor];
  const title = lang === 'tr' ? 'Orijinal' : 'Original';

  useEffect(() => {
    if (!container.current) return;
    let disposed = false;
    setReady(false); setFailed(false); setPlaying(false); setTime(0); setDuration(0);
    const ws = WaveSurfer.create({
      container: container.current, waveColor: '#62566f',
      progressColor: `rgb(${accent})`, cursorColor: '#d0c3ff',
      barWidth: 2.5, barGap: 2, barRadius: 3, height: 56,
    });
    player.current = ws;
    const fail = () => { if (!disposed) { setFailed(true); setReady(false); setPlaying(false); } };
    ws.on('ready', () => {
      setDuration(ws.getDuration()); setReady(true);
      ws.setVolume(volumeRef.current.volume); ws.setMuted(volumeRef.current.muted);
    });
    ws.on('play', () => setPlaying(true));
    ws.on('pause', () => setPlaying(false));
    ws.on('finish', () => setPlaying(false));
    ws.on('timeupdate', setTime);
    ws.on('error', fail);
    void ws.load(`/api/audio/source?path=${encodeURIComponent(source.path)}`).catch(fail);
    return () => { disposed = true; player.current = null; ws.destroy(); };
  }, [source.path, accent, retry]);

  return (
    <div style={{'--preset-accent': accent} as CSSProperties}
      className="stem-player border border-white/10 rounded-3xl p-5 sm:p-6 bg-gradient-to-br from-preset/5 via-[#211d2b] to-[#191621] shadow-xl shadow-black/10 space-y-4">
      <div className="flex items-start gap-3 min-w-0">
        <div className="rounded-xl bg-preset/10 p-3 text-preset"><Music size={20} /></div>
        <div className="min-w-0">
          <h4 className="text-lg font-bold text-white">{title}</h4>
          <p className="mt-1 text-sm text-slate-400 truncate" title={source.name}>{source.name}</p>
        </div>
      </div>
      <div className="track-playback">
        {!ready && !failed && <p role="status" className="flex items-center gap-2 text-sm text-slate-300"><Loader2 size={16} className="animate-spin" />{lang === 'tr' ? 'Ses hazırlanıyor…' : 'Loading audio…'}</p>}
        <div ref={container} className="w-full cursor-pointer" />
        <div className="flex items-center justify-between gap-3 pt-1">
          <div className="flex items-center gap-3">
            <button type="button" disabled={!ready} onClick={() => { void player.current?.playPause().catch(() => setFailed(true)); }}
              aria-label={playing ? (lang === 'tr' ? 'Duraklat' : 'Pause') : (lang === 'tr' ? 'Dinle' : 'Play')}
              className="flex h-11 w-11 items-center justify-center rounded-xl bg-preset text-slate-950 hover:brightness-110 disabled:opacity-40">
              {playing ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" />}
            </button>
            <div className="text-sm font-mono text-slate-300"><span className="font-bold text-white">{formatTime(time)}</span> / {formatTime(duration)}</div>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => { player.current?.setMuted(!muted); setMuted(!muted); }}
              aria-label={muted ? (lang === 'tr' ? 'Sesi aç' : 'Unmute') : (lang === 'tr' ? 'Sesi kapat' : 'Mute')}
              className="rounded-lg p-2 text-slate-300 hover:text-white">
              {muted || volume === 0 ? <VolumeX size={16} /> : <Volume2 size={16} />}
            </button>
            <input type="range" min="0" max="1" step="0.05" value={muted ? 0 : volume}
              aria-label={lang === 'tr' ? 'Ses seviyesi' : 'Volume'}
              onChange={event => { const value = Number(event.target.value); setVolume(value); setMuted(false); player.current?.setVolume(value); player.current?.setMuted(false); }}
              className="w-16 sm:w-20 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer" />
          </div>
        </div>
      </div>
      {failed && <p role="alert" className="text-sm text-amber-300">
        {lang === 'tr' ? 'Orijinal ses açılamadı. Kaynak dosya taşınmış veya silinmiş olabilir.' : 'Could not open the original audio. The source file may have been moved or deleted.'}
        {' '}<button type="button" className="underline" onClick={() => setRetry(value => value + 1)}>{lang === 'tr' ? 'Tekrar dene' : 'Retry'}</button>
      </p>}
      <p className="text-sm text-slate-400">{lang === 'tr' ? 'Ayrıştırma öncesindeki kayıt · Vokal ve enstrümanla karşılaştır.' : 'Source recording · Compare with vocals and instrumental.'}</p>
    </div>
  );
}
