'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Download,
  Sliders,
  RotateCcw,
  Sparkles,
  Music,
  Mic,
  Loader2,
  ArrowRightLeft,
} from 'lucide-react';
import { Language, AccentColor } from '@/lib/types';
import { cn, formatTime, getNoteName, chromaticNotes } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';
import { LyricsModal } from './LyricsModal';
import { VisualizerExportModal } from './VisualizerExportModal';
import { KaraokeStudioModal } from './KaraokeStudioModal';
import { RestoreModal } from './RestoreModal';
import { ABCompareModal } from './ABCompareModal';

interface StemAudioPlayerProps {
  stem: string;
  allStems?: string[];
  lang: Language;
  accentColor: AccentColor;
  onNewStemCreated?: (filename: string) => void;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const StemAudioPlayer: React.FC<StemAudioPlayerProps> = ({
  stem,
  allStems,
  lang,
  accentColor,
  onNewStemCreated,
  onNotify,
}) => {
  const t = (key: string) => getTranslation(lang, key);
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showKaraokeModal, setShowKaraokeModal] = useState(false);
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [showABCompareModal, setShowABCompareModal] = useState(false);

  const isRestoredStem = stem.startsWith('Restored_') || stem.startsWith('Denoised_');
  const counterpartStem = (() => {
    if (!allStems || allStems.length <= 1) return null;
    if (isRestoredStem) {
      const rawTarget = stem.replace(/^Restored_|^Denoised_/, '').replace(/_\d+\.flac$/, '').toLowerCase();
      return allStems.find((s) => s !== stem && s.toLowerCase().includes(rawTarget)) ||
             allStems.find((s) => !s.startsWith('Restored_') && !s.startsWith('Denoised_')) || null;
    } else {
      const baseStem = stem.replace(/\.[^/.]+$/, '').toLowerCase();
      return allStems.find((s) => (s.startsWith('Restored_') || s.startsWith('Denoised_')) && s.toLowerCase().includes(baseStem)) ||
             allStems.find((s) => s.startsWith('Restored_') || s.startsWith('Denoised_')) || null;
    }
  })();

  // Pitch & Tempo State
  const [showPitchTempo, setShowPitchTempo] = useState(false);
  const [pitchShift, setPitchShift] = useState(0);
  const [tempoFactor, setTempoFactor] = useState(1.0);
  const [isModifying, setIsModifying] = useState(false);

  const updateLivePlayback = useCallback((pitch: number, tempo: number) => {
    if (!wsRef.current) return;
    const media = wsRef.current.getMediaElement();
    if (media) {
      if (pitch !== 0) {
        const pitchRatio = Math.pow(2, pitch / 12);
        const effectiveRate = Math.max(0.2, Math.min(4.0, tempo * pitchRatio));
        try {
          (media as any).preservesPitch = false;
        } catch {}
        try {
          media.playbackRate = effectiveRate;
        } catch {}
      } else {
        try {
          (media as any).preservesPitch = true;
        } catch {}
        try {
          media.playbackRate = Math.max(0.2, Math.min(4.0, tempo));
        } catch {}
      }
    } else {
      try {
        wsRef.current.setPlaybackRate(tempo, pitch === 0);
      } catch {}
    }
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const colorMap: Record<AccentColor, { progress: string; cursor: string }> = {
      indigo: { progress: '#6366f1', cursor: '#818cf8' },
      emerald: { progress: '#10b981', cursor: '#34d399' },
      rose: { progress: '#f43f5e', cursor: '#fb7185' },
      amber: { progress: '#f59e0b', cursor: '#fbbf24' },
      violet: { progress: '#8b5cf6', cursor: '#a78bfa' },
    };
    const themeColors = colorMap[accentColor] || colorMap.indigo;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#334155',
      progressColor: themeColors.progress,
      cursorColor: themeColors.cursor,
      barWidth: 2.5,
      barGap: 2,
      barRadius: 3,
      height: 56,
      url: `/output/${encodeURIComponent(stem)}`,
    });

    ws.on('ready', () => {
      setDuration(ws.getDuration());
      updateLivePlayback(pitchShift, tempoFactor);
    });

    ws.on('play', () => setIsPlaying(true));
    ws.on('pause', () => setIsPlaying(false));

    ws.on('audioprocess', () => {
      setCurrentTime(ws.getCurrentTime());
    });

    ws.on('finish', () => {
      setIsPlaying(false);
    });

    ws.on('error', (e) => {
      console.warn('WaveSurfer error:', e);
    });

    wsRef.current = ws;

    return () => {
      try {
        ws.destroy();
      } catch (err) {}
    };
  }, [stem, accentColor]);

  // Update playback rate/pitch when state changes without destroying WaveSurfer
  useEffect(() => {
    updateLivePlayback(pitchShift, tempoFactor);
  }, [pitchShift, tempoFactor, updateLivePlayback]);

  const handleTogglePlay = () => {
    if (!wsRef.current) return;
    wsRef.current.playPause();
  };

  const handleToggleMute = () => {
    if (!wsRef.current) return;
    const newMuted = !isMuted;
    wsRef.current.setMuted(newMuted);
    setIsMuted(newMuted);
  };

  const handleVolumeChange = (val: number) => {
    if (!wsRef.current) return;
    setVolume(val);
    wsRef.current.setVolume(val);
    if (val > 0 && isMuted) {
      wsRef.current.setMuted(false);
      setIsMuted(false);
    }
  };

  const handlePitchChange = (newPitch: number) => {
    setPitchShift(newPitch);
    updateLivePlayback(newPitch, tempoFactor);
  };

  const handleTempoChange = (newTempo: number) => {
    setTempoFactor(newTempo);
    updateLivePlayback(pitchShift, newTempo);
  };

  const handleResetPitchTempo = () => {
    setPitchShift(0);
    setTempoFactor(1.0);
    updateLivePlayback(0, 1.0);
  };

  const handleExportStem = async () => {
    setIsModifying(true);
    try {
      const res = await api.modifyAudio({
        file_name: stem,
        pitch_semitones: pitchShift,
        tempo_factor: tempoFactor,
      });

      if (res.status === 'success') {
        onNotify('success', t('Process & Export New Stem'), res.filename);
        if (onNewStemCreated) onNewStemCreated(res.filename);
        setShowPitchTempo(false);
        handleResetPitchTempo();
      } else {
        onNotify('error', 'Export Failed', res.message || 'Error modifying audio');
      }
    } catch (e: any) {
      onNotify('error', 'Export Failed', e.message);
    } finally {
      setIsModifying(false);
    }
  };

  const isVocal = stem.toLowerCase().includes('vocal') || stem.toLowerCase().includes('vox');
  const isInst = stem.toLowerCase().includes('instrumental') || stem.toLowerCase().includes('inst') || stem.toLowerCase().includes('other');

  // New Feature States
  const [analysis, setAnalysis] = useState<{ bpm: number; key: string; camelot: string } | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isQuickCleaning, setIsQuickCleaning] = useState(false);
  const [showLyricsModal, setShowLyricsModal] = useState(false);
  const [showVisualizerModal, setShowVisualizerModal] = useState(false);

  // Auto-analyze audio key and BPM on mount
  useEffect(() => {
    let isMounted = true;
    const fetchAnalysis = async () => {
      setIsAnalyzing(true);
      try {
        const data = await api.analyzeAudio(stem);
        if (isMounted && data.key) {
          setAnalysis({
            bpm: data.bpm,
            key: data.key,
            camelot: data.camelot,
          });
        }
      } catch (e) {
        // silent fail
      } finally {
        if (isMounted) setIsAnalyzing(false);
      }
    };
    fetchAnalysis();
    return () => {
      isMounted = false;
    };
  }, [stem]);

  const [cleanProgress, setCleanProgress] = useState<number | null>(null);

  const handleQuickClean = async (cleanType: 'dereverb' | 'debleed') => {
    setIsQuickCleaning(true);
    setCleanProgress(10);
    try {
      const res = await api.quickClean({
        file_name: stem,
        clean_type: cleanType,
      });
      if (res.task_id) {
        onNotify(
          'info',
          cleanType === 'dereverb' ? '💧 De-Reverb Başlatıldı' : '✂️ De-Bleed Başlatıldı',
          'Arka planda 2. aşama stüdyo temizliği yapılıyor...'
        );

        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await api.getTaskStatus(res.task_id);
            const p = Math.round((statusRes.progress || 0.1) * 100);
            setCleanProgress(Math.max(10, Math.min(99, p)));

            if (statusRes.status === 'completed') {
              clearInterval(pollInterval);
              setIsQuickCleaning(false);
              setCleanProgress(null);

              const newStems = statusRes.stems || statusRes.results || [];
              const cleanedFile = newStems[0] || '';

              onNotify(
                'success',
                cleanType === 'dereverb' ? '💧 De-Reverb Tamamlandı!' : '✂️ De-Bleed Tamamlandı!',
                cleanedFile ? `Temizlenen ses: ${cleanedFile}` : 'İkinci aşama stüdyo temizliği başarıyla bitti.'
              );

              if (cleanedFile && onNewStemCreated) {
                onNewStemCreated(cleanedFile);
              }
            } else if (statusRes.status === 'failed') {
              clearInterval(pollInterval);
              setIsQuickCleaning(false);
              setCleanProgress(null);
              onNotify('error', 'Temizlik Başarısız', statusRes.error || statusRes.message || 'Hata oluştu');
            }
          } catch (err) {
            // silent polling retry
          }
        }, 1200);
      }
    } catch (e: any) {
      setIsQuickCleaning(false);
      setCleanProgress(null);
      onNotify('error', 'Temizlik Başarısız', e.message);
    }
  };

  return (
    <div
      className={cn(
        'border rounded-3xl p-5 sm:p-6 shadow-2xl backdrop-blur-xl space-y-4 transition-all duration-300 relative overflow-hidden',
        isVocal
          ? 'bg-gradient-to-br from-rose-950/25 via-slate-900/95 to-slate-950 border-rose-500/30 shadow-rose-950/20'
          : isInst
          ? 'bg-gradient-to-br from-emerald-950/25 via-slate-900/95 to-slate-950 border-emerald-500/30 shadow-emerald-950/20'
          : 'bg-slate-900/80 border-slate-800'
      )}
    >
      {/* ROW 1: Stem Identification Badge, Title & Key/BPM */}
      <div className="flex items-center justify-between gap-3 pb-3 border-b border-white/5">
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={cn(
              'px-3 py-1.5 rounded-xl border flex items-center gap-2 shrink-0 shadow-lg font-black text-xs uppercase tracking-wider font-outfit select-none',
              isVocal && 'bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-rose-500/10',
              isInst && 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-emerald-500/10',
              !isVocal && !isInst && 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
            )}
          >
            {isVocal ? (
              <>
                <Mic className="w-4 h-4 text-rose-400 fill-rose-400/20 shrink-0" />
                <span>VOKAL (İNSAN SESİ)</span>
              </>
            ) : isInst ? (
              <>
                <Music className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>ENSTRÜMANTAL (MÜZİK)</span>
              </>
            ) : (
              <>
                <Music className="w-4 h-4 text-indigo-400 shrink-0" />
                <span>AYRILMIŞ KANAL</span>
              </>
            )}
          </div>

          <div className="min-w-0">
            <h4 className="font-bold text-xs sm:text-sm text-white/90 truncate" title={stem}>
              {stem}
            </h4>
            {analysis && (
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-amber-400/90 mt-0.5">
                <span className="font-bold">🎼 {analysis.key} ({analysis.camelot})</span>
                <span className="text-slate-600">•</span>
                <span className="font-bold">⚡ {analysis.bpm} BPM</span>
              </div>
            )}
          </div>
        </div>

        {/* Quick Download icon top right */}
        <a
          href={`/output/${encodeURIComponent(stem)}`}
          download={stem}
          className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white transition-all active:scale-95 shrink-0"
          title={t('Download')}
        >
          <Download className="w-4 h-4" />
        </a>
      </div>

      {/* ROW 2: Action Controls Toolbar */}
      <div className="flex flex-wrap items-center gap-2 pt-0.5">
        {/* Quick 2-Pass Clean Button */}
        {isVocal && (
          <button
            onClick={() => handleQuickClean('dereverb')}
            disabled={isQuickCleaning}
            className="px-3 py-1.5 rounded-xl bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 border border-sky-500/30 text-xs font-bold transition-all flex items-center gap-1.5 active:scale-95 disabled:opacity-50"
            title="Vokal arkasındaki tüm oda yankısını siler"
          >
            {isQuickCleaning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <span>💧</span>}
            <span>{isQuickCleaning ? `Temizleniyor %${cleanProgress || 10}` : 'Yankıyı Sil'}</span>
          </button>
        )}

        {isInst && (
          <button
            onClick={() => handleQuickClean('debleed')}
            disabled={isQuickCleaning}
            className="px-3 py-1.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-xs font-bold transition-all flex items-center gap-1.5 active:scale-95 disabled:opacity-50"
            title="Enstrümantaldeki tüm artık vokal fısıltılarını kazır"
          >
            {isQuickCleaning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <span>✂️</span>}
            <span>{isQuickCleaning ? `Kazınıyor %${cleanProgress || 10}` : 'Kalıntıyı Kazı'}</span>
          </button>
        )}

        {/* AI Karaoke Lyrics Button */}
        {isVocal && (
          <button
            onClick={() => setShowLyricsModal(true)}
            className="px-3 py-1.5 rounded-xl bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 border border-indigo-500/30 text-xs font-bold transition-all flex items-center gap-1.5 active:scale-95"
            title="Şarkı Sözlerini (.LRC/.SRT) Çıkar & Oynat"
          >
            <span>🎤</span>
            <span>Sözler</span>
          </button>
        )}

        {/* 1080p YouTube Karaoke Video Generator */}
        <button
          onClick={() => setShowKaraokeModal(true)}
          className="px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500/20 to-orange-500/20 hover:from-amber-500/30 hover:to-orange-500/30 text-amber-300 border border-amber-500/40 text-xs font-bold transition-all flex items-center gap-1.5 active:scale-95 shadow-md shadow-amber-500/10"
          title="Şarkı sözlerini düzenleyip 1080p YouTube Karaoke Videosu (MP4) Oluştur"
        >
          <span>🎤</span>
          <span>Karaoke Video</span>
        </button>

        {/* 1080p Video Visualizer Export */}
        <button
          onClick={() => setShowVisualizerModal(true)}
          className="px-3 py-1.5 rounded-xl bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 border border-indigo-500/30 text-xs font-bold transition-all flex items-center gap-1.5 active:scale-95"
          title="1080p Dalga Formlu Video (TikTok/Reels/YouTube) Oluştur"
        >
          <span>🎬</span>
          <span>Video Klip</span>
        </button>

        {/* AI Restoration & Super-Resolution (AudioSR + Roformer Denoise) */}
        <button
          onClick={() => setShowRestoreModal(true)}
          className="px-3 py-1.5 rounded-xl bg-gradient-to-r from-cyan-500/20 via-teal-500/20 to-indigo-500/20 hover:from-cyan-500/30 hover:to-indigo-500/30 text-cyan-300 border border-cyan-500/40 text-xs font-bold transition-all flex items-center gap-1.5 active:scale-95 shadow-md shadow-cyan-500/10"
          title="AudioSR + Roformer Denoise ile 48kHz Stüdyo Master Restorasyonu"
        >
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          <span>AI Onar & Parlat</span>
        </button>

        {/* Instant A/B Quality Comparison Button (Available when paired stem exists) */}
        {counterpartStem && (
          <button
            onClick={() => setShowABCompareModal(true)}
            className="px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500/20 via-cyan-500/20 to-indigo-500/20 hover:from-amber-500/30 hover:to-cyan-500/30 text-white border border-cyan-500/40 text-xs font-bold transition-all flex items-center gap-1.5 active:scale-95 shadow-md shadow-cyan-500/10"
            title="Orijinal ve Onarılmış ses arasındaki kalite farkını canlı senkronize dinleyin ve spektrumu inceleyin"
          >
            <ArrowRightLeft className="w-3.5 h-3.5 text-cyan-300" />
            <span>A/B Karşılaştır</span>
          </button>
        )}

        {/* Pitch & Tempo Toggle */}
        <button
          onClick={() => setShowPitchTempo(!showPitchTempo)}
          className={cn(
            'px-3 py-1.5 rounded-xl border text-xs font-bold transition-all flex items-center gap-1.5 active:scale-95',
            showPitchTempo || pitchShift !== 0 || tempoFactor !== 1.0
              ? 'bg-violet-500/25 border-violet-500/50 text-violet-300'
              : 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white'
          )}
        >
          <Sliders className="w-3.5 h-3.5" />
          <span>{t('Pitch & Tempo Editor')}</span>
        </button>
      </div>

      {/* Waveform Player */}
      <div className="bg-slate-950/60 p-4 rounded-2xl border border-slate-800/80 space-y-3">
        <div ref={containerRef} className="w-full cursor-pointer" />

        {/* Player Controls */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-3">
            {/* Play/Pause Button */}
            <button
              onClick={handleTogglePlay}
              className={cn(
                'w-10 h-10 rounded-xl flex items-center justify-center text-white shadow-lg transition-transform active:scale-90',
                accentColor === 'indigo' && 'bg-indigo-600 hover:bg-indigo-500',
                accentColor === 'emerald' && 'bg-emerald-600 hover:bg-emerald-500',
                accentColor === 'rose' && 'bg-rose-600 hover:bg-rose-500',
                accentColor === 'amber' && 'bg-amber-600 hover:bg-amber-500',
                accentColor === 'violet' && 'bg-violet-600 hover:bg-violet-500'
              )}
            >
              {isPlaying ? <Pause className="w-5 h-5 fill-white" /> : <Play className="w-5 h-5 fill-white ml-0.5" />}
            </button>

            {/* Time Indicator */}
            <div className="text-xs font-mono text-slate-400">
              <span className="text-white font-bold">{formatTime(currentTime)}</span> /{' '}
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          {/* Volume Control */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleToggleMute}
              className="text-slate-400 hover:text-white transition-colors"
            >
              {isMuted || volume === 0 ? (
                <VolumeX className="w-4 h-4 text-rose-400" />
              ) : (
                <Volume2 className="w-4 h-4" />
              )}
            </button>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={isMuted ? 0 : volume}
              onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
              className="w-20 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
          </div>
        </div>
      </div>

      {/* Pitch & Tempo Interactive Panel */}
      {showPitchTempo && (
        <div className="p-6 rounded-2xl bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 border border-violet-500/20 space-y-6">
          {/* Header & Reset Button */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-400" />
              <h5 className="text-sm font-bold text-white font-outfit">
                {t('Pitch & Tempo Editor')}
              </h5>
            </div>
            {(pitchShift !== 0 || tempoFactor !== 1.0) && (
              <button
                onClick={handleResetPitchTempo}
                className="text-xs text-violet-300 hover:text-white px-2.5 py-1 rounded-lg bg-violet-500/20 hover:bg-violet-500/30 transition-all font-mono font-medium flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>{t('Reset')}</span>
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Pitch / Musical Note Slider */}
            <div className="space-y-3">
              <div className="flex justify-between items-end">
                <label className="text-xs font-bold text-violet-400 uppercase tracking-widest">
                  {t('Pitch (Semitones)')}
                </label>
                <div className="flex items-center gap-1.5">
                  <span className="text-xl font-mono font-bold text-white">
                    {pitchShift > 0 ? `+${pitchShift}` : pitchShift}
                  </span>
                  <span className="text-xs font-mono font-bold text-violet-300 px-2 py-0.5 rounded bg-violet-500/20 border border-violet-500/30">
                    {getNoteName(pitchShift, lang)}
                  </span>
                </div>
              </div>

              <input
                type="range"
                min="-12"
                max="12"
                step="1"
                value={pitchShift}
                onChange={(e) => handlePitchChange(parseInt(e.target.value, 10))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-violet-500"
              />

              <div className="flex justify-between text-[10px] text-slate-500 font-bold uppercase">
                <span>-12 (Do↓)</span>
                <span>0 (Do)</span>
                <span>+12 (Do↑)</span>
              </div>

              {/* 12-TET Chromatic Note Buttons */}
              <div className="pt-2">
                <div className="text-[10px] font-bold text-slate-400 mb-2 uppercase tracking-wider flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <span>🎵</span>
                    <span>{t('Quick Note Selection')}</span>
                  </span>
                  <span className="text-[9px] text-violet-400 font-mono">12-TET Scale</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {chromaticNotes.map((n) => {
                    const isSelected = pitchShift === n.semitones;
                    return (
                      <button
                        key={n.semitones}
                        type="button"
                        onClick={() => handlePitchChange(n.semitones)}
                        className={cn(
                          'px-2 py-0.5 text-[10px] rounded border transition-all active:scale-95 font-mono',
                          isSelected
                            ? 'bg-violet-600 text-white font-bold border-violet-400 shadow-md shadow-violet-500/40 ring-1 ring-violet-400'
                            : 'bg-slate-900/80 hover:bg-slate-800 text-slate-300 border-slate-700/60 hover:text-white'
                        )}
                      >
                        {lang === 'en' ? n.labelEN : n.labelTR}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Tempo (Speed) Controls */}
            <div className="space-y-3">
              <div className="flex justify-between items-end">
                <label className="text-xs font-bold text-fuchsia-400 uppercase tracking-widest">
                  {t('Tempo (Speed)')}
                </label>
                <span className="text-xl font-mono font-bold text-white">{tempoFactor}x</span>
              </div>

              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.05"
                value={tempoFactor}
                onChange={(e) => handleTempoChange(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-fuchsia-500"
              />

              <div className="flex justify-between text-[10px] text-slate-500 font-bold uppercase">
                <span>0.5x</span>
                <span>1.0x</span>
                <span>2.0x</span>
              </div>

              {/* Quick Tempo Buttons */}
              <div className="pt-2">
                <div className="text-[10px] font-bold text-slate-400 mb-2 uppercase tracking-wider flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <span>⚡</span>
                    <span>BPM / Speed</span>
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {[0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0].map((spd) => (
                    <button
                      key={spd}
                      type="button"
                      onClick={() => handleTempoChange(spd)}
                      className={cn(
                        'px-2 py-0.5 text-[10px] rounded border transition-all active:scale-95 font-mono',
                        tempoFactor === spd
                          ? 'bg-fuchsia-600 text-white font-bold border-fuchsia-400 shadow-md shadow-fuchsia-500/40 ring-1 ring-fuchsia-400'
                          : 'bg-slate-900/80 hover:bg-slate-800 text-slate-300 border-slate-700/60 hover:text-white'
                      )}
                    >
                      {spd}x
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Process & Export Button */}
          <button
            onClick={handleExportStem}
            disabled={isModifying}
            className="w-full py-3.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-xl shadow-violet-500/20 active:scale-95 disabled:opacity-50"
          >
            {isModifying ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>{t('Processing Audio...')}</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>{t('Process & Export New Stem')}</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Synchronized Live Lyrics Modal */}
      <LyricsModal
        isOpen={showLyricsModal}
        onClose={() => setShowLyricsModal(false)}
        fileName={stem}
        currentTime={currentTime}
        isPlaying={isPlaying}
        onTogglePlay={handleTogglePlay}
        onSeek={(time) => {
          if (wsRef.current) {
            const dur = wsRef.current.getDuration();
            if (dur > 0) {
              wsRef.current.seekTo(time / dur);
            }
          }
        }}
        lang={lang}
        onNotify={onNotify}
      />

      {/* 1080p Video Visualizer Export Modal */}
      <VisualizerExportModal
        isOpen={showVisualizerModal}
        onClose={() => setShowVisualizerModal(false)}
        fileName={stem}
        lang={lang}
        onNotify={onNotify}
      />

      {/* 1080p YouTube Karaoke Studio & Video Generator Modal */}
      <KaraokeStudioModal
        isOpen={showKaraokeModal}
        onClose={() => setShowKaraokeModal(false)}
        instStem={stem}
        vocalStem={
          allStems?.find(
            (s) =>
              s.toLowerCase().includes('vocal') ||
              s.toLowerCase().includes('vok')
          ) || (isVocal ? stem : undefined)
        }
        lang={lang}
        onNotify={onNotify}
      />

      {/* AI Audio Restoration & Super-Resolution Modal */}
      <RestoreModal
        isOpen={showRestoreModal}
        onClose={() => setShowRestoreModal(false)}
        stem={stem}
        lang={lang}
        onNewStemCreated={onNewStemCreated}
        onNotify={onNotify}
      />

      {/* Synchronized A/B Quality Comparison Modal */}
      {counterpartStem && (
        <ABCompareModal
          isOpen={showABCompareModal}
          onClose={() => setShowABCompareModal(false)}
          originalFile={isRestoredStem ? counterpartStem : stem}
          restoredFile={isRestoredStem ? stem : counterpartStem}
          lang={lang}
        />
      )}
    </div>
  );
};
