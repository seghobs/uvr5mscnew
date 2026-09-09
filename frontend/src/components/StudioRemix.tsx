'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Sliders, Play, Square, Sparkles, Loader2, Volume2 } from 'lucide-react';
import { Language, AccentColor } from '@/lib/types';
import { cn, formatTime } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';

interface StudioRemixProps {
  stems: string[];
  lang: Language;
  accentColor: AccentColor;
  onNewRemixCreated: (filename: string) => void;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const StudioRemix: React.FC<StudioRemixProps> = ({
  stems,
  lang,
  accentColor,
  onNewRemixCreated,
  onNotify,
}) => {
  const t = (key: string) => getTranslation(lang, key);

  const vocalStem = stems.find((s) => s.toLowerCase().includes('vocal')) || '';
  const instStem =
    stems.find((s) => s.toLowerCase().includes('instrumental') || s.toLowerCase().includes('inst')) ||
    '';

  const [vocalGain, setVocalGain] = useState(0);
  const [instGain, setInstGain] = useState(0);
  const [remixPitch, setRemixPitch] = useState(0);
  const [remixTempo, setRemixTempo] = useState(1.0);

  // 3-Band Parametric EQ State
  const [bassGain, setBassGain] = useState(0);
  const [midGain, setMidGain] = useState(0);
  const [trebleGain, setTrebleGain] = useState(0);
  const [activeAB, setActiveAB] = useState<'remix' | 'vocal_only' | 'inst_only'>('remix');

  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isPreparingPreview, setIsPreparingPreview] = useState(false);
  const [isRemixing, setIsRemixing] = useState(false);
  const [previewTime, setPreviewTime] = useState(0);
  const [previewDuration, setPreviewDuration] = useState(0);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const vocalSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const instSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const vocalGainNodeRef = useRef<GainNode | null>(null);
  const instGainNodeRef = useRef<GainNode | null>(null);
  
  // EQ Filter Nodes
  const bassFilterRef = useRef<BiquadFilterNode | null>(null);
  const midFilterRef = useRef<BiquadFilterNode | null>(null);
  const trebleFilterRef = useRef<BiquadFilterNode | null>(null);

  const vocalBufferRef = useRef<AudioBuffer | null>(null);
  const instBufferRef = useRef<AudioBuffer | null>(null);
  const startTimeRef = useRef<number>(0);
  const offsetRef = useRef<number>(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const eqCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const previewRequestRef = useRef(0);
  const bufferKeyRef = useRef('');

  // Stop audio on unmount
  useEffect(() => {
    return () => {
      stopPreview();
    };
  }, [vocalStem, instStem]);

  // Draw dynamic EQ response curve on canvas
  useEffect(() => {
    const canvas = eqCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    // Background grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 20) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Zero dB center line
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();

    // Draw Smooth EQ Curve
    const midY = height / 2;
    const bassOffset = -(bassGain / 12) * (height / 2.8);
    const midOffset = -(midGain / 12) * (height / 2.8);
    const trebleOffset = -(trebleGain / 12) * (height / 2.8);

    ctx.beginPath();
    ctx.moveTo(0, midY + bassOffset);
    ctx.bezierCurveTo(
      width * 0.25,
      midY + bassOffset,
      width * 0.35,
      midY + midOffset,
      width * 0.5,
      midY + midOffset
    );
    ctx.bezierCurveTo(
      width * 0.65,
      midY + midOffset,
      width * 0.75,
      midY + trebleOffset,
      width,
      midY + trebleOffset
    );

    // Glowing EQ Stroke
    ctx.strokeStyle = '#d946ef';
    ctx.lineWidth = 3;
    ctx.shadowColor = 'rgba(217, 70, 239, 0.6)';
    ctx.shadowBlur = 10;
    ctx.stroke();

    // Gradient fill under curve
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, 'rgba(217, 70, 239, 0.2)');
    grad.addColorStop(1, 'rgba(217, 70, 239, 0.0)');
    ctx.fillStyle = grad;
    ctx.fill();
  }, [bassGain, midGain, trebleGain]);

  const loadAudioBuffer = async (url: string, ctx: AudioContext): Promise<AudioBuffer> => {
    const res = await fetch(url);
    const arrayBuf = await res.arrayBuffer();
    return ctx.decodeAudioData(arrayBuf);
  };

  const startPreview = async () => {
    if (!vocalStem || !instStem) return;
    const requestId = ++previewRequestRef.current;
    setIsPreparingPreview(true);
    try {
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const ctx = audioCtxRef.current;
      if (ctx.state === 'suspended') await ctx.resume();

      const key = JSON.stringify([vocalStem, instStem, remixPitch, remixTempo]);
      if (bufferKeyRef.current !== key || !vocalBufferRef.current || !instBufferRef.current) {
        const prepare = async (file: string) => {
          if (remixPitch === 0 && remixTempo === 1) return file;
          const result = await api.modifyAudio({file_name: file, pitch_semitones: remixPitch, tempo_factor: remixTempo});
          if (!result.filename) throw new Error(result.message || 'Önizleme sesi hazırlanamadı.');
          return result.filename;
        };
        const vocalFile = await prepare(vocalStem);
        const instFile = await prepare(instStem);
        const [vocal, inst] = await Promise.all([
          loadAudioBuffer(`/output/${encodeURIComponent(vocalFile)}`, ctx),
          loadAudioBuffer(`/output/${encodeURIComponent(instFile)}`, ctx),
        ]);
        if (requestId !== previewRequestRef.current) return;
        vocalBufferRef.current = vocal; instBufferRef.current = inst; bufferKeyRef.current = key;
      }
      if (requestId !== previewRequestRef.current) return;
      const playbackDuration = Math.max(vocalBufferRef.current.duration, instBufferRef.current.duration);
      setPreviewDuration(playbackDuration);

      const vSource = ctx.createBufferSource();
      const iSource = ctx.createBufferSource();
      const vGain = ctx.createGain();
      const iGain = ctx.createGain();

      // Create 3-Band Parametric Filters
      const bassFilter = ctx.createBiquadFilter();
      bassFilter.type = 'lowshelf';
      bassFilter.frequency.value = 100;
      bassFilter.gain.value = bassGain;

      const midFilter = ctx.createBiquadFilter();
      midFilter.type = 'peaking';
      midFilter.frequency.value = 1000;
      midFilter.Q.value = 1.0;
      midFilter.gain.value = midGain;

      const trebleFilter = ctx.createBiquadFilter();
      trebleFilter.type = 'highshelf';
      trebleFilter.frequency.value = 10000;
      trebleFilter.gain.value = trebleGain;

      vSource.buffer = vocalBufferRef.current;
      iSource.buffer = instBufferRef.current;

      // Apply initial gains
      const vVol = activeAB === 'inst_only' ? 0 : Math.pow(10, vocalGain / 20);
      const iVol = activeAB === 'vocal_only' ? 0 : Math.pow(10, instGain / 20);
      vGain.gain.value = vVol;
      iGain.gain.value = iVol;

      // Apply Pitch & Tempo
      // The server uses the same independent pitch/tempo processing as export.
      vSource.playbackRate.value = 1;
      iSource.playbackRate.value = 1;

      // Connect Graph: Sources -> Gains -> Master EQ -> Destination
      vSource.connect(vGain);
      iSource.connect(iGain);
      vGain.connect(bassFilter);
      iGain.connect(bassFilter);
      bassFilter.connect(midFilter);
      midFilter.connect(trebleFilter);
      trebleFilter.connect(ctx.destination);

      vSource.start(0, offsetRef.current);
      iSource.start(0, offsetRef.current);

      vocalSourceRef.current = vSource;
      instSourceRef.current = iSource;
      vocalGainNodeRef.current = vGain;
      instGainNodeRef.current = iGain;
      bassFilterRef.current = bassFilter;
      midFilterRef.current = midFilter;
      trebleFilterRef.current = trebleFilter;

      startTimeRef.current = ctx.currentTime;
      setIsPreviewing(true);

      timerRef.current = setInterval(() => {
        if (!audioCtxRef.current) return;
        const elapsed = audioCtxRef.current.currentTime - startTimeRef.current;
        const current = offsetRef.current + elapsed;
        setPreviewTime(current);
        if (current >= playbackDuration) {
          stopPreview();
        }
      }, 100);

      let remaining = 2;
      const ended = () => { if (--remaining === 0 && requestId === previewRequestRef.current) stopPreview(); };
      vSource.onended = ended;
      iSource.onended = ended;
    } catch (e: any) {
      onNotify('error', 'Preview Error', e.message);
    } finally { if (requestId === previewRequestRef.current) setIsPreparingPreview(false); }
  };

  const stopPreview = () => {
    previewRequestRef.current++;
    setIsPreparingPreview(false);
    if (timerRef.current) clearInterval(timerRef.current);
    try {
      vocalSourceRef.current?.stop();
      instSourceRef.current?.stop();
    } catch {}
    setIsPreviewing(false);
    offsetRef.current = 0;
    setPreviewTime(0);
  };

  const handleVocalGainChange = (val: number) => {
    setVocalGain(val);
    if (vocalGainNodeRef.current && activeAB !== 'inst_only') {
      vocalGainNodeRef.current.gain.value = Math.pow(10, val / 20);
    }
  };

  const handleInstGainChange = (val: number) => {
    setInstGain(val);
    if (instGainNodeRef.current && activeAB !== 'vocal_only') {
      instGainNodeRef.current.gain.value = Math.pow(10, val / 20);
    }
  };

  const handleBassChange = (val: number) => {
    setBassGain(val);
    if (bassFilterRef.current) bassFilterRef.current.gain.value = val;
  };

  const handleMidChange = (val: number) => {
    setMidGain(val);
    if (midFilterRef.current) midFilterRef.current.gain.value = val;
  };

  const handleTrebleChange = (val: number) => {
    setTrebleGain(val);
    if (trebleFilterRef.current) trebleFilterRef.current.gain.value = val;
  };

  const handleABSwitch = (mode: 'remix' | 'vocal_only' | 'inst_only') => {
    setActiveAB(mode);
    if (vocalGainNodeRef.current && instGainNodeRef.current) {
      if (mode === 'remix') {
        vocalGainNodeRef.current.gain.value = Math.pow(10, vocalGain / 20);
        instGainNodeRef.current.gain.value = Math.pow(10, instGain / 20);
      } else if (mode === 'vocal_only') {
        vocalGainNodeRef.current.gain.value = Math.pow(10, vocalGain / 20);
        instGainNodeRef.current.gain.value = 0;
      } else if (mode === 'inst_only') {
        vocalGainNodeRef.current.gain.value = 0;
        instGainNodeRef.current.gain.value = Math.pow(10, instGain / 20);
      }
    }
  };

  const handleRemixPitchChange = (val: number) => {
    stopPreview();
    setRemixPitch(val);
  };

  const handleRemixTempoChange = (val: number) => {
    stopPreview();
    setRemixTempo(val);
  };

  const handleExportRemix = async () => {
    if (!vocalStem || !instStem) return;
    setIsRemixing(true);
    try {
      const res = await api.remixAudio({
        vocal_file: vocalStem,
        inst_file: instStem,
        vocal_gain: vocalGain,
        inst_gain: instGain,
        pitch_shift: remixPitch,
        tempo_factor: remixTempo,
        out_format: 'mp3',
      });
      onNotify('success', t('Remerge & Export Remix'), res.filename);
      onNewRemixCreated(res.filename);
    } catch (e: any) {
      onNotify('error', 'Remix Export Failed', e.message);
    } finally {
      setIsRemixing(false);
    }
  };

  if (!vocalStem || !instStem) return null;

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 shadow-2xl backdrop-blur-xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Sliders className="w-5 h-5 text-fuchsia-400" />
          <h3 className="text-base font-bold font-outfit text-white">{t('Studio Remix & Merge')}</h3>
        </div>
        {previewDuration > 0 && (
          <div className="text-xs font-mono text-slate-400">
            <span className="text-white font-bold">{formatTime(previewTime)}</span> /{' '}
            <span>{formatTime(previewDuration)}</span>
          </div>
        )}
      </div>

      {/* Gain & Pitch / Tempo Sliders */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6">
        {/* Vocal Gain */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-bold text-rose-400 uppercase">
            <span>{t('Vocal Gain')}</span>
            <span className="font-mono text-white">{vocalGain > 0 ? `+${vocalGain}` : vocalGain} dB</span>
          </div>
          <input
            type="range"
            min="-30"
            max="16"
            step="1"
            value={vocalGain}
            onChange={(e) => handleVocalGainChange(parseInt(e.target.value, 10))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-rose-500"
          />
        </div>

        {/* Instrumental Gain */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-bold text-emerald-400 uppercase">
            <span>{t('Instrumental Gain')}</span>
            <span className="font-mono text-white">{instGain > 0 ? `+${instGain}` : instGain} dB</span>
          </div>
          <input
            type="range"
            min="-30"
            max="16"
            step="1"
            value={instGain}
            onChange={(e) => handleInstGainChange(parseInt(e.target.value, 10))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
          />
        </div>

        {/* Master Pitch */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-bold text-violet-400 uppercase">
            <span>{t('Master Pitch (Semitones)')}</span>
            <span className="font-mono text-white">{remixPitch > 0 ? `+${remixPitch}` : remixPitch}</span>
          </div>
          <input
            type="range"
            min="-12"
            max="12"
            step="1"
            value={remixPitch}
            onChange={(e) => handleRemixPitchChange(parseInt(e.target.value, 10))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-violet-500"
          />
        </div>

        {/* Master Tempo */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-bold text-fuchsia-400 uppercase">
            <span>{t('Master Tempo (Speed)')}</span>
            <span className="font-mono text-white">{remixTempo}x</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.05"
            value={remixTempo}
            onChange={(e) => handleRemixTempoChange(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-fuchsia-500"
          />
        </div>
      </div>

      {/* 3-Band Visual Parametric EQ & A/B Switcher Section */}
      <div className="p-5 rounded-2xl bg-slate-950/70 border border-white/5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm">🎛️</span>
            <div>
              <h4 className="text-xs font-black font-outfit text-white uppercase tracking-wider">
                3-Bant Görsel Parametrik EQ & Master Mastering
              </h4>
              <span className="text-[10px] text-slate-400">Canlı Web Audio Biquad Filtresi</span>
            </div>
          </div>

          {/* Seamless A/B Comparator Switcher */}
          <div className="flex items-center gap-1.5 p-1 bg-slate-900 rounded-xl border border-white/5 self-start sm:self-auto">
            <button
              type="button"
              onClick={() => handleABSwitch('remix')}
              className={cn(
                'px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all',
                activeAB === 'remix'
                  ? 'bg-fuchsia-600 text-white shadow-md shadow-fuchsia-600/30'
                  : 'text-slate-400 hover:text-white'
              )}
            >
              Full Master (A+B)
            </button>
            <button
              type="button"
              onClick={() => handleABSwitch('vocal_only')}
              className={cn(
                'px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all',
                activeAB === 'vocal_only'
                  ? 'bg-rose-600 text-white shadow-md shadow-rose-600/30'
                  : 'text-slate-400 hover:text-white'
              )}
            >
              Solo Vokal (A)
            </button>
            <button
              type="button"
              onClick={() => handleABSwitch('inst_only')}
              className={cn(
                'px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all',
                activeAB === 'inst_only'
                  ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30'
                  : 'text-slate-400 hover:text-white'
              )}
            >
              Solo Enstrümantal (B)
            </button>
          </div>
        </div>

        {/* Visual Frequency Response Curve Canvas */}
        <div className="relative rounded-xl overflow-hidden bg-slate-950 border border-white/10 h-24 flex items-center justify-center">
          <canvas
            ref={eqCanvasRef}
            width={600}
            height={96}
            className="w-full h-full object-cover"
          />
          <div className="absolute top-2 left-3 flex items-center gap-4 text-[9px] font-mono text-slate-400">
            <span>LOW: 100Hz ({bassGain > 0 ? `+${bassGain}` : bassGain}dB)</span>
            <span>MID: 1kHz ({midGain > 0 ? `+${midGain}` : midGain}dB)</span>
            <span>HIGH: 10kHz ({trebleGain > 0 ? `+${trebleGain}` : trebleGain}dB)</span>
          </div>
        </div>

        {/* 3-Band Sliders Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
          {/* Bass Low-Shelf */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-[10px] font-bold text-slate-300 uppercase">
              <span>Bas (100 Hz)</span>
              <span className="font-mono text-fuchsia-400">{bassGain > 0 ? `+${bassGain}` : bassGain} dB</span>
            </div>
            <input
              type="range"
              min="-12"
              max="12"
              step="1"
              value={bassGain}
              onChange={(e) => handleBassChange(parseInt(e.target.value, 10))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-fuchsia-500"
            />
          </div>

          {/* Mid Peaking */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-[10px] font-bold text-slate-300 uppercase">
              <span>Mid / Gövde (1 kHz)</span>
              <span className="font-mono text-fuchsia-400">{midGain > 0 ? `+${midGain}` : midGain} dB</span>
            </div>
            <input
              type="range"
              min="-12"
              max="12"
              step="1"
              value={midGain}
              onChange={(e) => handleMidChange(parseInt(e.target.value, 10))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-fuchsia-500"
            />
          </div>

          {/* Treble High-Shelf */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-[10px] font-bold text-slate-300 uppercase">
              <span>Tiz / Hava (10 kHz)</span>
              <span className="font-mono text-fuchsia-400">{trebleGain > 0 ? `+${trebleGain}` : trebleGain} dB</span>
            </div>
            <input
              type="range"
              min="-12"
              max="12"
              step="1"
              value={trebleGain}
              onChange={(e) => handleTrebleChange(parseInt(e.target.value, 10))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-fuchsia-500"
            />
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={isPreviewing ? stopPreview : startPreview}
          disabled={isPreparingPreview}
          className={cn(
            'flex-1 py-3.5 rounded-2xl font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-lg active:scale-95 text-white',
            isPreviewing
              ? 'bg-rose-600 hover:bg-rose-500 shadow-rose-500/20'
              : 'bg-slate-800 hover:bg-slate-700 border border-slate-700'
          )}
        >
          {isPreparingPreview ? <><Loader2 className="w-4 h-4 animate-spin"/><span>Önizleme hazırlanıyor…</span></> : isPreviewing ? (
            <>
              <Square className="w-4 h-4 fill-white" />
              <span>{t('Stop Preview')}</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-white" />
              <span>{t('Preview Mix')}</span>
            </>
          )}
        </button>

        <button
          onClick={handleExportRemix}
          disabled={isRemixing}
          className="flex-1 py-3.5 rounded-2xl font-bold text-xs bg-gradient-to-r from-fuchsia-600 to-violet-600 hover:from-fuchsia-500 hover:to-violet-500 text-white flex items-center justify-center gap-2 shadow-xl shadow-fuchsia-500/25 active:scale-95 disabled:opacity-50"
        >
          {isRemixing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>{t('Mixing Stems...')}</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>{t('Remerge & Export Remix')}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
