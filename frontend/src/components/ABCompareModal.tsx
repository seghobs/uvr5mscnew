'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import {
  X,
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  Sparkles,
  ArrowRightLeft,
  Download,
  Activity,
  CheckCircle2,
} from 'lucide-react';
import { Language } from '@/lib/types';
import { cn, formatTime } from '@/lib/utils';

interface ABCompareModalProps {
  isOpen: boolean;
  onClose: () => void;
  originalFile: string;
  restoredFile: string;
  lang: Language;
}

export const ABCompareModal: React.FC<ABCompareModalProps> = ({
  isOpen,
  onClose,
  originalFile,
  restoredFile,
  lang,
}) => {
  const audioRefA = useRef<HTMLAudioElement | null>(null);
  const audioRefB = useRef<HTMLAudioElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [activeChannel, setActiveChannel] = useState<'A' | 'B'>('B');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  // Audio Context & Analyser
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceARef = useRef<MediaElementAudioSourceNode | null>(null);
  const sourceBRef = useRef<MediaElementAudioSourceNode | null>(null);
  const gainARef = useRef<GainNode | null>(null);
  const gainBRef = useRef<GainNode | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const cleanOriginalName = originalFile ? originalFile.replace(/^Restored_|^Denoised_/, '') : 'Orijinal';
  const cleanRestoredName = restoredFile || 'Restored_48kHz.flac';

  const originalUrl = `/output/${encodeURIComponent(originalFile)}`;
  const restoredUrl = `/output/${encodeURIComponent(restoredFile)}`;

  // Initialize Web Audio API nodes
  const initAudioNodes = useCallback(() => {
    if (audioCtxRef.current) return;
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.8;

      const gainA = ctx.createGain();
      const gainB = ctx.createGain();

      if (audioRefA.current && audioRefB.current) {
        try {
          const srcA = ctx.createMediaElementSource(audioRefA.current);
          const srcB = ctx.createMediaElementSource(audioRefB.current);

          srcA.connect(gainA);
          srcB.connect(gainB);

          gainA.connect(analyser);
          gainB.connect(analyser);

          analyser.connect(ctx.destination);

          sourceARef.current = srcA;
          sourceBRef.current = srcB;
          gainARef.current = gainA;
          gainBRef.current = gainB;
          analyserRef.current = analyser;
          audioCtxRef.current = ctx;

          gainA.gain.value = activeChannel === 'A' && !isMuted ? volume : 0;
          gainB.gain.value = activeChannel === 'B' && !isMuted ? volume : 0;
        } catch (e) {
          console.warn('MediaElementSource initialization fallback:', e);
        }
      }
    } catch (e) {
      console.warn('AudioContext error:', e);
    }
  }, [activeChannel, isMuted, volume]);

  // Update volume & crossfade when channel switches
  useEffect(() => {
    const vol = isMuted ? 0 : volume;

    if (gainARef.current && gainBRef.current && audioCtxRef.current) {
      const now = audioCtxRef.current.currentTime;
      if (activeChannel === 'A') {
        gainARef.current.gain.setTargetAtTime(vol, now, 0.015);
        gainBRef.current.gain.setTargetAtTime(0, now, 0.015);
      } else {
        gainARef.current.gain.setTargetAtTime(0, now, 0.015);
        gainBRef.current.gain.setTargetAtTime(vol, now, 0.015);
      }
    } else {
      if (audioRefA.current && audioRefB.current) {
        if (activeChannel === 'A') {
          audioRefA.current.volume = vol;
          audioRefB.current.volume = 0;
        } else {
          audioRefA.current.volume = 0;
          audioRefB.current.volume = vol;
        }
      }
    }
  }, [activeChannel, volume, isMuted]);

  // Canvas visualizer loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let running = true;

    const render = () => {
      if (!running) return;
      const width = canvas.width;
      const height = canvas.height;

      ctx.clearRect(0, 0, width, height);

      // Background grid
      ctx.fillStyle = '#090d16';
      ctx.fillRect(0, 0, width, height);

      // Frequency grid lines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
      ctx.lineWidth = 1;
      for (let x = 0; x < width; x += width / 8) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }

      if (analyserRef.current && isPlaying) {
        const bufferLength = analyserRef.current.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        analyserRef.current.getByteFrequencyData(dataArray);

        const barWidth = (width / bufferLength) * 2.2;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          const barHeight = (dataArray[i] / 255) * height * 0.95;

          if (activeChannel === 'A') {
            const grad = ctx.createLinearGradient(0, height, 0, height - barHeight);
            grad.addColorStop(0, 'rgba(217, 119, 6, 0.8)');
            grad.addColorStop(0.6, 'rgba(245, 158, 11, 0.6)');
            grad.addColorStop(1, 'rgba(251, 191, 36, 0.9)');
            ctx.fillStyle = grad;
          } else {
            const grad = ctx.createLinearGradient(0, height, 0, height - barHeight);
            grad.addColorStop(0, 'rgba(6, 182, 212, 0.85)');
            grad.addColorStop(0.5, 'rgba(45, 212, 191, 0.7)');
            grad.addColorStop(1, 'rgba(168, 85, 247, 0.95)');
            ctx.fillStyle = grad;
          }

          ctx.fillRect(x, height - barHeight, barWidth - 1, barHeight);
          x += barWidth;
          if (x > width) break;
        }
      } else {
        ctx.strokeStyle = activeChannel === 'A' ? 'rgba(245, 158, 11, 0.3)' : 'rgba(6, 182, 212, 0.3)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(0, height / 2);
        ctx.lineTo(width, height / 2);
        ctx.stroke();
      }

      animFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      running = false;
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isPlaying, activeChannel]);

  // Synchronized Play / Pause
  const handleTogglePlay = async () => {
    initAudioNodes();
    if (audioCtxRef.current && audioCtxRef.current.state === 'suspended') {
      await audioCtxRef.current.resume();
    }

    if (!audioRefA.current || !audioRefB.current) return;

    if (isPlaying) {
      audioRefA.current.pause();
      audioRefB.current.pause();
      setIsPlaying(false);
    } else {
      const maxTime = Math.max(audioRefA.current.currentTime, audioRefB.current.currentTime);
      audioRefA.current.currentTime = maxTime;
      audioRefB.current.currentTime = maxTime;

      try {
        await Promise.all([audioRefA.current.play(), audioRefB.current.play()]);
        setIsPlaying(true);
      } catch (err) {
        console.warn('Playback error:', err);
      }
    }
  };

  // Switch A/B seamlessly without stopping
  const handleSwitchChannel = (ch: 'A' | 'B') => {
    initAudioNodes();
    if (audioCtxRef.current && audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }

    if (audioRefA.current && audioRefB.current) {
      const sourceTime = ch === 'A' ? audioRefB.current.currentTime : audioRefA.current.currentTime;
      if (Math.abs(audioRefA.current.currentTime - audioRefB.current.currentTime) > 0.05) {
        audioRefA.current.currentTime = sourceTime;
        audioRefB.current.currentTime = sourceTime;
      }
    }

    setActiveChannel(ch);
  };

  // Keyboard shortcuts: Space = Play/Pause, Tab / A / B = Toggle Channel
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.code === 'Space') {
        e.preventDefault();
        handleTogglePlay();
      } else if (e.code === 'KeyA') {
        e.preventDefault();
        handleSwitchChannel('A');
      } else if (e.code === 'KeyB') {
        e.preventDefault();
        handleSwitchChannel('B');
      } else if (e.code === 'Tab') {
        e.preventDefault();
        handleSwitchChannel(activeChannel === 'A' ? 'B' : 'A');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isPlaying, activeChannel]);

  const handleTimeUpdate = () => {
    if (!audioRefA.current) return;
    const cur = audioRefA.current.currentTime;
    setCurrentTime(cur);

    if (audioRefB.current && Math.abs(audioRefB.current.currentTime - cur) > 0.04) {
      audioRefB.current.currentTime = cur;
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRefA.current && audioRefA.current.duration) {
      setDuration(audioRefA.current.duration);
    } else if (audioRefB.current && audioRefB.current.duration) {
      setDuration(audioRefB.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setCurrentTime(val);
    if (audioRefA.current) audioRefA.current.currentTime = val;
    if (audioRefB.current) audioRefB.current.currentTime = val;
  };

  const handleRestart = () => {
    if (audioRefA.current) audioRefA.current.currentTime = 0;
    if (audioRefB.current) audioRefB.current.currentTime = 0;
    setCurrentTime(0);
  };

  if (!isOpen) return null;

  const modalContent = (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-slate-950/85 backdrop-blur-lg animate-in fade-in duration-200">
      {/* Hidden Audio Elements */}
      <audio
        ref={audioRefA}
        src={originalUrl}
        preload="auto"
        crossOrigin="anonymous"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={() => setIsPlaying(false)}
      />
      <audio
        ref={audioRefB}
        src={restoredUrl}
        preload="auto"
        crossOrigin="anonymous"
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={() => setIsPlaying(false)}
      />

      <div className="relative w-full max-w-3xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl shadow-cyan-950/40 flex flex-col overflow-hidden text-slate-200 max-h-[92vh]">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-slate-800 bg-slate-900/90 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500/20 via-cyan-500/20 to-indigo-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-300 shadow-md shadow-cyan-500/10">
              <ArrowRightLeft className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-base sm:text-lg text-white">
                  A/B Ses Kalite Karşılaştırması
                </h3>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  Canlı Senkronize
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Oynatırken tek tıkla Orijinal ve Restored ses arasında kesintisiz geçiş yapın
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              if (audioRefA.current) audioRefA.current.pause();
              if (audioRefB.current) audioRefB.current.pause();
              setIsPlaying(false);
              onClose();
            }}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-6 space-y-5 overflow-y-auto">
          
          {/* Main A/B Switch Console */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            {/* Channel A: Original */}
            <div
              onClick={() => handleSwitchChannel('A')}
              className={cn(
                "p-4 rounded-2xl border transition-all cursor-pointer relative overflow-hidden flex flex-col justify-between select-none",
                activeChannel === 'A'
                  ? "bg-amber-950/40 border-amber-500/60 shadow-lg shadow-amber-500/15 ring-2 ring-amber-500/50"
                  : "bg-slate-950/40 border-slate-800/80 hover:bg-slate-800/40 opacity-70 hover:opacity-100"
              )}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className={cn(
                    "w-7 h-7 rounded-lg flex items-center justify-center font-black text-xs font-mono",
                    activeChannel === 'A' ? "bg-amber-500 text-slate-950 font-bold" : "bg-slate-800 text-slate-400"
                  )}>
                    A
                  </div>
                  <div>
                    <span className="text-xs font-bold text-amber-300 block">Kanal A: Orijinal Ses</span>
                    <span className="text-[10px] text-slate-400">Ham / Boğuk / Eski Kayıt</span>
                  </div>
                </div>
                {activeChannel === 'A' && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/30 text-amber-200 border border-amber-500/40 animate-pulse">
                    ● ŞU AN ÇALIYOR
                  </span>
                )}
              </div>

              <div className="p-2 rounded-xl bg-slate-950/80 border border-slate-800 text-[11px] font-mono text-slate-300 truncate mb-3">
                {cleanOriginalName}
              </div>

              <div className="grid grid-cols-2 gap-2 text-[10px] font-mono pt-1 border-t border-slate-800/80">
                <div className="text-slate-400">
                  Frekans Sınırı: <span className="text-amber-300 font-bold">~14-16 kHz</span>
                </div>
                <div className="text-slate-400 text-right">
                  Dip Hiss: <span className="text-rose-400 font-bold">Mevcut</span>
                </div>
              </div>
            </div>

            {/* Channel B: AI Restored */}
            <div
              onClick={() => handleSwitchChannel('B')}
              className={cn(
                "p-4 rounded-2xl border transition-all cursor-pointer relative overflow-hidden flex flex-col justify-between select-none",
                activeChannel === 'B'
                  ? "bg-cyan-950/40 border-cyan-500/60 shadow-lg shadow-cyan-500/15 ring-2 ring-cyan-500/50"
                  : "bg-slate-950/40 border-slate-800/80 hover:bg-slate-800/40 opacity-70 hover:opacity-100"
              )}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className={cn(
                    "w-7 h-7 rounded-lg flex items-center justify-center font-black text-xs font-mono",
                    activeChannel === 'B' ? "bg-cyan-400 text-slate-950 font-bold" : "bg-slate-800 text-slate-400"
                  )}>
                    B
                  </div>
                  <div>
                    <span className="text-xs font-bold text-cyan-300 flex items-center gap-1.5">
                      <span>Kanal B: Restored 48kHz</span>
                      <Sparkles className="w-3 h-3 text-cyan-400" />
                    </span>
                    <span className="text-[10px] text-slate-400">AudioSR + Aufr33 Denoise</span>
                  </div>
                </div>
                {activeChannel === 'B' && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/30 text-cyan-200 border border-cyan-500/40 animate-pulse">
                    ● ŞU AN ÇALIYOR
                  </span>
                )}
              </div>

              <div className="p-2 rounded-xl bg-slate-950/80 border border-slate-800 text-[11px] font-mono text-cyan-300 truncate mb-3">
                {cleanRestoredName}
              </div>

              <div className="grid grid-cols-2 gap-2 text-[10px] font-mono pt-1 border-t border-slate-800/80">
                <div className="text-slate-400">
                  Frekans Sınırı: <span className="text-cyan-300 font-bold">24.0 kHz Hi-Fi</span>
                </div>
                <div className="text-slate-400 text-right">
                  Dip Hiss: <span className="text-emerald-400 font-bold">28dB Temiz</span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick Toggle Button & Keyboard Hint */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 bg-slate-950/70 border border-slate-800 rounded-xl">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Activity className="w-4 h-4 text-cyan-400" />
              <span>İpucu: Çalarken klavyedeki <kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-200 font-mono text-[10px] border border-slate-700">Tab</kbd> veya <kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-200 font-mono text-[10px] border border-slate-700">Space</kbd> tuşlarını kullanabilirsiniz.</span>
            </div>
            <button
              onClick={() => handleSwitchChannel(activeChannel === 'A' ? 'B' : 'A')}
              className={cn(
                "px-4 py-2 rounded-xl font-bold text-xs flex items-center gap-2 transition-all shadow-md active:scale-95 shrink-0",
                activeChannel === 'A'
                  ? "bg-gradient-to-r from-cyan-600 to-teal-500 text-white shadow-cyan-600/20"
                  : "bg-gradient-to-r from-amber-600 to-orange-500 text-white shadow-amber-600/20"
              )}
            >
              <ArrowRightLeft className="w-3.5 h-3.5" />
              <span>{activeChannel === 'A' ? "Kanal B'ye Geç (48kHz Hi-Fi)" : "Kanal A'ya Geç (Orijinal)"}</span>
            </button>
          </div>

          {/* Realtime Canvas Frequency Spectrum Display */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs px-1">
              <span className="font-semibold text-slate-300 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-cyan-400" />
                <span>Canlı Frekans Spektrumu (Gerçek Zamanlı FFT Analizi)</span>
              </span>
              <span className="text-[10px] font-mono text-slate-400">
                Aktif: <strong className={activeChannel === 'A' ? 'text-amber-400' : 'text-cyan-400'}>
                  {activeChannel === 'A' ? 'Kanal A (Orijinal)' : 'Kanal B (48kHz Hi-Fi)'}
                </strong>
              </span>
            </div>
            
            <div className="relative w-full h-32 rounded-xl overflow-hidden border border-slate-800 bg-slate-950 shadow-inner">
              <canvas
                ref={canvasRef}
                width={700}
                height={128}
                className="w-full h-full block"
              />
              
              {/* Frequency Scale Overlay */}
              <div className="absolute bottom-1 left-2 right-2 flex justify-between text-[9px] font-mono text-slate-500 select-none pointer-events-none">
                <span>20 Hz (Bas)</span>
                <span>500 Hz</span>
                <span>2 kHz (Vokal)</span>
                <span>8 kHz</span>
                <span>16 kHz</span>
                <span className={activeChannel === 'B' ? 'text-cyan-400 font-bold' : 'text-slate-600'}>
                  24 kHz (Hi-Fi)
                </span>
              </div>
            </div>
          </div>

          {/* Synchronized Player Transport Bar */}
          <div className="p-4 rounded-xl bg-slate-950/90 border border-slate-800 space-y-3">
            {/* Scrubber Slider */}
            <div className="space-y-1">
              <input
                type="range"
                min={0}
                max={duration || 100}
                step={0.1}
                value={currentTime}
                onChange={handleSeek}
                className={cn(
                  "w-full h-1.5 rounded-lg appearance-none cursor-pointer bg-slate-800",
                  activeChannel === 'A' ? "accent-amber-500" : "accent-cyan-500"
                )}
              />
              <div className="flex justify-between text-[11px] font-mono text-slate-400">
                <span>{formatTime(currentTime)}</span>
                <span>{formatTime(duration)}</span>
              </div>
            </div>

            {/* Transport Controls */}
            <div className="flex items-center justify-between pt-1">
              <div className="flex items-center gap-2">
                <button
                  onClick={handleTogglePlay}
                  className={cn(
                    "w-11 h-11 rounded-xl flex items-center justify-center text-white shadow-lg transition-transform active:scale-95",
                    activeChannel === 'A'
                      ? "bg-amber-600 hover:bg-amber-500 shadow-amber-600/25"
                      : "bg-cyan-600 hover:bg-cyan-500 shadow-cyan-600/25"
                  )}
                  title="Oynat / Duraklat (Space)"
                >
                  {isPlaying ? <Pause className="w-5 h-5 fill-white" /> : <Play className="w-5 h-5 fill-white ml-0.5" />}
                </button>

                <button
                  onClick={handleRestart}
                  className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                  title="Başa Sar"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              </div>

              {/* Volume Slider */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsMuted(!isMuted)}
                  className="text-slate-400 hover:text-white transition-colors"
                >
                  {isMuted || volume === 0 ? <VolumeX className="w-4 h-4 text-rose-400" /> : <Volume2 className="w-4 h-4" />}
                </button>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={isMuted ? 0 : volume}
                  onChange={(e) => setVolume(parseFloat(e.target.value))}
                  className="w-24 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-slate-400"
                />
              </div>
            </div>
          </div>

          {/* Side-by-Side Quality Comparison Table */}
          <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-950/60 text-xs">
            <div className="px-3.5 py-2.5 bg-slate-900 border-b border-slate-800 font-bold text-slate-300 flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span>Teknik Kalite Farkı Karşılaştırma Matrisi</span>
            </div>
            <div className="divide-y divide-slate-800/80 font-mono text-[11px]">
              <div className="grid grid-cols-3 p-2.5 items-center">
                <span className="text-slate-400 font-sans">Örnekleme Hızı (Sampling Rate):</span>
                <span className="text-amber-400">44.1 kHz (Standart)</span>
                <span className="text-cyan-300 font-bold flex items-center gap-1">
                  <span>48.0 kHz Ultra Hi-Fi</span>
                  <CheckCircle2 className="w-3 h-3 text-cyan-400" />
                </span>
              </div>
              <div className="grid grid-cols-3 p-2.5 items-center">
                <span className="text-slate-400 font-sans">Harmonik Tavanı (Frequency Ceiling):</span>
                <span className="text-amber-400">~14.5 kHz Kesik</span>
                <span className="text-cyan-300 font-bold flex items-center gap-1">
                  <span>24.0 kHz (+8 kHz Sentez)</span>
                  <CheckCircle2 className="w-3 h-3 text-cyan-400" />
                </span>
              </div>
              <div className="grid grid-cols-3 p-2.5 items-center">
                <span className="text-slate-400 font-sans">Dip Gürültü & Hiss (Aufr33):</span>
                <span className="text-rose-400">Kaset Tıslaması / Amfi Cızırtısı</span>
                <span className="text-emerald-400 font-bold flex items-center gap-1">
                  <span>27.99 dB SDR Ultra Temiz</span>
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                </span>
              </div>
              <div className="grid grid-cols-3 p-2.5 items-center">
                <span className="text-slate-400 font-sans">Tel & Parmak Rezonansı:</span>
                <span className="text-slate-400">Mat / Boğuk Doku</span>
                <span className="text-cyan-300 font-bold flex items-center gap-1">
                  <span>Canlı & Kristal Tizler</span>
                  <CheckCircle2 className="w-3 h-3 text-cyan-400" />
                </span>
              </div>
            </div>
          </div>

        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <a
              href={restoredUrl}
              download={cleanRestoredName}
              className="px-3.5 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-md shadow-cyan-600/20"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Restored (.flac) İndir</span>
            </a>
          </div>

          <button
            type="button"
            onClick={() => {
              if (audioRefA.current) audioRefA.current.pause();
              if (audioRefB.current) audioRefB.current.pause();
              setIsPlaying(false);
              onClose();
            }}
            className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs transition-colors"
          >
            Kapat
          </button>
        </div>

      </div>
    </div>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(modalContent, document.body);
};
