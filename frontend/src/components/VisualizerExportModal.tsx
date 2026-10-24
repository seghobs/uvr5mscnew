'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  Video,
  X,
  Download,
  Loader2,
  Sparkles,
  Smartphone,
  Monitor,
  CheckCircle2,
  Play,
  Palette,
} from 'lucide-react';
import { Language } from '@/lib/types';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface VisualizerExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileName: string;
  lang: Language;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const VisualizerExportModal: React.FC<VisualizerExportModalProps> = ({
  isOpen,
  onClose,
  fileName,
  lang,
  onNotify,
}) => {
  const t = (key: string) => getTranslation(lang, key);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const [aspectRatio, setAspectRatio] = useState<'9:16' | '16:9'>('9:16');
  const [theme, setTheme] = useState<'neon' | 'gold' | 'cyberpunk'>('neon');
  const [title, setTitle] = useState(fileName.replace(/\.[^/.]+$/, ''));
  const [rendering, setRendering] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  if (!isOpen || !mounted) return null;

  const handleGenerate = async () => {
    setRendering(true);
    setVideoUrl(null);
    try {
      const res = await api.generateVisualizer({
        file_name: fileName,
        aspect_ratio: aspectRatio,
        theme: theme,
        title: title,
      });
      if (res.download_url) {
        setVideoUrl(res.download_url);
        onNotify('success', 'Video Hazırlandı!', '1080p Video Visualizer başarıyla oluşturuldu.');
      }
    } catch (err: any) {
      onNotify('error', 'Render Başarısız', err.message || 'Video oluşturulamadı');
    } finally {
      setRendering(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xl animate-fade-in">
      <div className="relative w-full max-w-lg bg-slate-900/90 border border-white/10 rounded-3xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-5 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-amber-500/15 text-amber-400 border border-amber-500/30">
              <Video className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-black font-outfit text-white tracking-tight">
                  1080p Video Visualizer
                </h3>
                <span className="text-[9px] font-bold font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                  MP4 EXPORT
                </span>
              </div>
              <p className="text-[11px] text-slate-400 truncate max-w-xs">{fileName}</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-white/[0.05] hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5">
          {/* Format Selection (9:16 Vertical vs 16:9 Landscape) */}
          <div className="space-y-2">
            <label className="text-[11px] font-bold text-slate-300 uppercase tracking-widest block">
              Format & En-Boy Oranı
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setAspectRatio('9:16')}
                className={cn(
                  'p-3.5 rounded-2xl border flex items-center gap-3 transition-all text-left group',
                  aspectRatio === '9:16'
                    ? 'bg-indigo-600/20 border-indigo-500/60 shadow-lg shadow-indigo-500/10'
                    : 'bg-slate-950/60 border-white/5 hover:border-white/20'
                )}
              >
                <div
                  className={cn(
                    'p-2.5 rounded-xl transition-colors',
                    aspectRatio === '9:16' ? 'bg-indigo-600 text-white' : 'bg-white/5 text-slate-400'
                  )}
                >
                  <Smartphone className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-xs font-bold text-white block">9:16 Dikey Video</span>
                  <span className="text-[10px] text-slate-400 block">TikTok / Reels / Shorts</span>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setAspectRatio('16:9')}
                className={cn(
                  'p-3.5 rounded-2xl border flex items-center gap-3 transition-all text-left group',
                  aspectRatio === '16:9'
                    ? 'bg-indigo-600/20 border-indigo-500/60 shadow-lg shadow-indigo-500/10'
                    : 'bg-slate-950/60 border-white/5 hover:border-white/20'
                )}
              >
                <div
                  className={cn(
                    'p-2.5 rounded-xl transition-colors',
                    aspectRatio === '16:9' ? 'bg-indigo-600 text-white' : 'bg-white/5 text-slate-400'
                  )}
                >
                  <Monitor className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-xs font-bold text-white block">16:9 Yatay Video</span>
                  <span className="text-[10px] text-slate-400 block">YouTube / Full HD TV</span>
                </div>
              </button>
            </div>
          </div>

          {/* Color Theme Selector */}
          <div className="space-y-2">
            <label className="text-[11px] font-bold text-slate-300 uppercase tracking-widest flex items-center gap-1.5">
              <Palette className="w-3.5 h-3.5 text-indigo-400" />
              <span>Görsel Tema & Spektrum</span>
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setTheme('neon')}
                className={cn(
                  'p-3 rounded-2xl border text-center transition-all',
                  theme === 'neon'
                    ? 'bg-indigo-500/20 border-indigo-500 text-white shadow-md'
                    : 'bg-slate-950/60 border-white/5 text-slate-400 hover:text-white'
                )}
              >
                <div className="w-4 h-4 rounded-full bg-gradient-to-r from-indigo-500 to-indigo-400 mx-auto mb-1.5 shadow-sm" />
                <span className="text-xs font-bold block">Neon Sky</span>
              </button>

              <button
                type="button"
                onClick={() => setTheme('gold')}
                className={cn(
                  'p-3 rounded-2xl border text-center transition-all',
                  theme === 'gold'
                    ? 'bg-indigo-500/20 border-indigo-500 text-white shadow-md'
                    : 'bg-slate-950/60 border-white/5 text-slate-400 hover:text-white'
                )}
              >
                <div className="w-4 h-4 rounded-full bg-gradient-to-r from-indigo-400 to-indigo-600 mx-auto mb-1.5 shadow-sm" />
                <span className="text-xs font-bold block">Gold Studio</span>
              </button>

              <button
                type="button"
                onClick={() => setTheme('cyberpunk')}
                className={cn(
                  'p-3 rounded-2xl border text-center transition-all',
                  theme === 'cyberpunk'
                    ? 'bg-rose-500/20 border-rose-500 text-white shadow-md'
                    : 'bg-slate-950/60 border-white/5 text-slate-400 hover:text-white'
                )}
              >
                <div className="w-4 h-4 rounded-full bg-gradient-to-r from-indigo-500 via-indigo-500 to-indigo-400 mx-auto mb-1.5 shadow-sm" />
                <span className="text-xs font-bold block">Cyberpunk</span>
              </button>
            </div>
          </div>

          {/* Title Input */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest block">
              Video Başlığı
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-slate-950/80 border border-white/10 rounded-2xl p-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              placeholder="Şarkı adı..."
            />
          </div>

          {/* Render Result / Video Preview */}
          {videoUrl && (
            <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-between gap-3 animate-fade-in">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                <div>
                  <p className="text-xs font-bold text-emerald-300">Video Hazır!</p>
                  <span className="text-[10px] text-emerald-400/80 font-mono">1080p MP4 Formatında</span>
                </div>
              </div>
              <a
                href={videoUrl}
                download
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-lg shadow-emerald-600/30 transition-transform active:scale-95"
              >
                <Download className="w-4 h-4" />
                <span>İndir (MP4)</span>
              </a>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-5 border-t border-white/10 bg-slate-950/60 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 rounded-xl bg-white/[0.05] hover:bg-white/10 text-slate-300 font-bold text-xs transition-colors"
          >
            Kapat
          </button>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={rendering}
            className="px-5 py-2.5 rounded-2xl bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-slate-950 font-black text-xs flex items-center gap-2 shadow-lg shadow-indigo-500/20 transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            {rendering ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>1080p Render Ediliyor...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Video Oluştur</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
