'use client';

import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import {
  Mic2,
  X,
  Download,
  FileText,
  Loader2,
  Play,
  Pause,
  Copy,
  Check,
  Music2,
  Database,
  Sparkles,
} from 'lucide-react';
import { LyricSegment, Language } from '@/lib/types';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';
import { cn, formatTime } from '@/lib/utils';

interface LyricsModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileName: string;
  currentTime?: number;
  onSeek?: (time: number) => void;
  isPlaying?: boolean;
  onTogglePlay?: () => void;
  lang: Language;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const LyricsModal: React.FC<LyricsModalProps> = ({
  isOpen,
  onClose,
  fileName,
  currentTime = 0,
  onSeek,
  isPlaying = false,
  onTogglePlay,
  lang,
  onNotify,
}) => {
  const t = (key: string) => getTranslation(lang, key);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const [loading, setLoading] = useState(false);
  const [segments, setSegments] = useState<LyricSegment[]>([]);
  const [lrcContent, setLrcContent] = useState('');
  const [srtContent, setSrtContent] = useState('');
  const [copied, setCopied] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState<'tr' | 'en'>('tr');

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const activeLineRef = useRef<HTMLDivElement>(null);

  const [isCached, setIsCached] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && fileName) {
      loadLyrics(false);
    }
  }, [isOpen, fileName, selectedLanguage]);

  const loadLyrics = async (force = false) => {
    setLoading(true);
    try {
      const res = await api.transcribeLyrics(fileName, selectedLanguage, force);
      if (res.segments) {
        setSegments(res.segments);
        setLrcContent(res.lrc_content || '');
        setSrtContent(res.srt_content || '');
        setIsCached(!!res.cached);
        if (res.updated_at) {
          setUpdatedAt(new Date(res.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        }
      }
    } catch (err: any) {
      onNotify('error', 'Söz Çıkarma Başarısız', err.message || 'Sözler analiz edilemedi');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeLineRef.current && scrollContainerRef.current) {
      activeLineRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [currentTime]);

  if (!isOpen) return null;

  const currentSegmentIndex = segments.findIndex(
    (s, idx) =>
      currentTime >= s.start &&
      (currentTime < s.end || idx === segments.length - 1 || currentTime < (segments[idx + 1]?.start || s.end + 2))
  );

  const downloadFile = (content: string, ext: 'lrc' | 'srt') => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileName.replace(/\.[^/.]+$/, '')}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
    onNotify('success', 'İndirildi', `.${ext.toUpperCase()} dosyası kaydedildi.`);
  };

  const copyToClipboard = () => {
    const fullText = segments.map((s) => s.text).join('\n');
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onNotify('info', 'Kopyalandı', 'Tüm şarkı sözleri panoya kopyalandı.');
  };

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xl animate-fade-in">
      <div className="relative w-full max-w-2xl bg-slate-900/90 border border-white/10 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="p-5 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
              <Mic2 className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-black font-outfit text-white tracking-tight">
                  AI Senkronize Şarkı Sözleri
                </h3>
                <span className="text-[9px] font-bold font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
                  WHISPER SYNC
                </span>
              </div>
              <p className="text-[11px] text-slate-400 truncate max-w-md">{fileName}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={copyToClipboard}
              className="p-2 rounded-xl bg-white/[0.05] hover:bg-white/10 text-slate-300 transition-colors"
              title="Sözleri Kopyala"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-white/[0.05] hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="px-5 py-3 border-b border-white/5 bg-slate-950/40 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedLanguage('tr')}
              className={cn(
                'px-2.5 py-1 rounded-lg text-xs font-bold transition-all',
                selectedLanguage === 'tr'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-white bg-white/5'
              )}
            >
              🇹🇷 Türkçe
            </button>
            <button
              onClick={() => setSelectedLanguage('en')}
              className={cn(
                'px-2.5 py-1 rounded-lg text-xs font-bold transition-all',
                selectedLanguage === 'en'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-white bg-white/5'
              )}
            >
              🇬🇧 English / Diğer
            </button>

            {isCached && (
              <span
                title="Şarkı sözleri SQLite veritabanından anında yüklendi"
                className="hidden sm:flex items-center gap-1 text-[10px] font-bold text-emerald-300 bg-emerald-500/10 px-2 py-0.5 rounded-lg border border-emerald-500/20"
              >
                <Database className="w-3 h-3 text-emerald-400" />
                <span>SQLite {updatedAt ? `(${updatedAt})` : 'Kayıtlı'}</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => loadLyrics(true)}
              disabled={loading}
              title="Whisper AI ile şarkı sözlerini sıfırdan baştan çıkar"
              className="px-2.5 py-1.5 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold flex items-center gap-1.5 transition-all active:scale-95 disabled:opacity-40"
            >
              {loading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Sparkles className="w-3.5 h-3.5" />
              )}
              <span className="hidden sm:inline">AI ile Yeniden Çıkar</span>
            </button>

            <button
              onClick={() => downloadFile(lrcContent, 'lrc')}
              disabled={!lrcContent}
              className="px-3 py-1.5 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold flex items-center gap-1.5 transition-all disabled:opacity-40"
              title="Karaoke Oynatıcıları için .LRC İndir"
            >
              <Download className="w-3.5 h-3.5" />
              <span>.LRC İndir</span>
            </button>
            <button
              onClick={() => downloadFile(srtContent, 'srt')}
              disabled={!srtContent}
              className="px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/10 text-slate-300 border border-white/10 text-xs font-bold flex items-center gap-1.5 transition-all disabled:opacity-40"
              title="Video Altyazıları için .SRT İndir"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>.SRT İndir</span>
            </button>
          </div>
        </div>

        {/* Live Scrolling Lyrics View */}
        <div
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto p-6 space-y-5 text-center scroll-smooth min-h-[320px] max-h-[500px]"
        >
          {loading ? (
            <div className="h-64 flex flex-col items-center justify-center gap-3 text-slate-400">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
              <p className="text-sm font-semibold">Şarkı sözleri yapay zeka ile çözümleniyor...</p>
            </div>
          ) : segments.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center gap-2 text-slate-500">
              <Music2 className="w-10 h-10 stroke-1" />
              <p className="text-sm">Bu parça için şarkı sözü bulunamadı veya enstrümantal.</p>
            </div>
          ) : (
            segments.map((seg, idx) => {
              const isActive = idx === currentSegmentIndex;
              const isPast = idx < currentSegmentIndex;

              return (
                <div
                  key={idx}
                  ref={isActive ? activeLineRef : null}
                  onClick={() => onSeek && onSeek(seg.start)}
                  className={cn(
                    'py-2 px-4 rounded-2xl cursor-pointer transition-all duration-300 group',
                    isActive
                      ? 'bg-indigo-500/15 border border-indigo-500/30 scale-105 shadow-lg shadow-indigo-500/10'
                      : isPast
                      ? 'text-slate-500 hover:text-slate-300 opacity-60'
                      : 'text-slate-400 hover:text-white opacity-90'
                  )}
                >
                  <p
                    className={cn(
                      'font-outfit transition-all duration-300 tracking-tight',
                      isActive
                        ? 'text-xl sm:text-2xl font-black text-indigo-300 drop-shadow-[0_0_12px_rgba(99,102,241,0.5)]'
                        : 'text-base sm:text-lg font-medium group-hover:scale-102'
                    )}
                  >
                    {seg.text}
                  </p>
                  <span
                    className={cn(
                      'text-[10px] font-mono block mt-1 transition-opacity',
                      isActive ? 'text-indigo-400 font-bold opacity-100' : 'text-slate-600 opacity-0 group-hover:opacity-100'
                    )}
                  >
                    {formatTime(seg.start)} - {formatTime(seg.end)}
                  </span>
                </div>
              );
            })
          )}
        </div>

        {/* Footer Playback Control */}
        <div className="p-4 border-t border-white/10 bg-slate-950/60 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {onTogglePlay && (
              <button
                onClick={onTogglePlay}
                className="w-10 h-10 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center shadow-lg shadow-indigo-600/30 transition-transform active:scale-95"
              >
                {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
              </button>
            )}
            <div>
              <p className="text-xs font-bold text-white font-mono">{formatTime(currentTime)}</p>
              <span className="text-[10px] text-slate-400">Canlı Zaman Damgası</span>
            </div>
          </div>

          <div className="text-right">
            <span className="text-[10px] text-slate-500">Satıra tıklayarak doğrudan o saniyeye atlayabilirsiniz</span>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};
