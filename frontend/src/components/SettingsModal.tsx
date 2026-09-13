'use client';

import React, { useState } from 'react';
import { X, Cpu, Sliders, CheckCircle2, Trash2, AlertTriangle, Loader2 } from 'lucide-react';
import { Language, AccentColor, SeparationParams } from '@/lib/types';
import { cn } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';
import { flushAllProjects, initializeProjects } from '@/lib/project-storage';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  lang: Language;
  accentColor: AccentColor;
  device: string;
  onChangeDevice: (dev: string) => void;
  params: SeparationParams;
  onChangeParams: (params: SeparationParams) => void;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  lang,
  accentColor,
  device,
  onChangeDevice,
  params,
  onChangeParams,
  onNotify,
}) => {
  const t = (key: string) => getTranslation(lang, key);
  const [isClearingKaraoke, setIsClearingKaraoke] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  const handleClearKaraoke = async () => {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    setIsClearingKaraoke(true);
    try {
      await flushAllProjects();
      const res = await api.clearKaraokeData();
      await initializeProjects();
      onNotify(
        'success',
        lang === 'tr' ? 'Karaoke Veritabanı Temizlendi' : 'Karaoke Database Cleared',
        lang === 'tr'
          ? `${res.deleted_lyrics_count} şarkı sözü kaydı ve ${res.deleted_files_count} dosya başarıyla silindi.`
          : `Wiped ${res.deleted_lyrics_count} lyrics rows and ${res.deleted_files_count} output files.`
      );
      setConfirmClear(false);
      window.location.reload();
    } catch (err: any) {
      onNotify('error', 'Hata', err.message || 'Karaoke verileri temizlenemedi.');
    } finally {
      setIsClearingKaraoke(false);
    }
  };

  const accentCardMap: Record<AccentColor, { card: string; icon: string; btn: string; confirmBtn: string }> = {
    indigo: {
      card: 'bg-indigo-500/10 border-indigo-500/30',
      icon: 'text-indigo-400',
      btn: 'bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 border-indigo-500/30',
      confirmBtn: 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/30',
    },
    emerald: {
      card: 'bg-emerald-500/10 border-emerald-500/30',
      icon: 'text-emerald-400',
      btn: 'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border-emerald-500/30',
      confirmBtn: 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/30',
    },
    rose: {
      card: 'bg-rose-500/10 border-rose-500/30',
      icon: 'text-rose-400',
      btn: 'bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border-rose-500/30',
      confirmBtn: 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/30',
    },
    amber: {
      card: 'bg-amber-500/10 border-amber-500/30',
      icon: 'text-amber-400',
      btn: 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border-amber-500/30',
      confirmBtn: 'bg-amber-600 hover:bg-amber-500 text-white shadow-amber-600/30',
    },
    violet: {
      card: 'bg-violet-500/10 border-violet-500/30',
      icon: 'text-violet-400',
      btn: 'bg-violet-500/20 hover:bg-violet-500/30 text-violet-300 border-violet-500/30',
      confirmBtn: 'bg-violet-600 hover:bg-violet-500 text-white shadow-violet-600/30',
    },
  };

  const themeStyle = accentCardMap[accentColor] || accentCardMap.indigo;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="bg-slate-900 border border-slate-700/80 rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-6 animate-in fade-in zoom-in-95 duration-200">
        {/* Modal Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Sliders className={cn('w-5 h-5', themeStyle.icon)} />
            <h3 className="text-base font-bold font-outfit text-white">{t('Global Settings')}</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Compute Device */}
        <div className="space-y-3">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block">
            {t('Compute Device')}
          </label>
          <div className="grid grid-cols-2 gap-3">
            {[
              { id: 'CUDA (Auto)', label: 'NVIDIA CUDA (Auto)', desc: 'GPU Accelerated' },
              { id: 'CPU', label: 'CPU (Direct)', desc: 'Compatibility Mode' },
            ].map((dev) => (
              <button
                key={dev.id}
                type="button"
                onClick={() => onChangeDevice(dev.id)}
                className={cn(
                  'p-3.5 rounded-2xl border text-left transition-all',
                  device === dev.id
                    ? `${themeStyle.card} text-white`
                    : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-white'
                )}
              >
                <div className="flex items-center gap-2 font-bold text-xs">
                  <Cpu className={cn('w-4 h-4', themeStyle.icon)} />
                  <span>{dev.label}</span>
                </div>
                <span className="text-[10px] text-slate-500 mt-1 block font-mono">{dev.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Advanced Audio Normalization Thresholds */}
        <div className="space-y-4 pt-2 border-t border-slate-800">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block">
            {t('Processing Parameters')}
          </label>

          <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-300">
              <span>Normalization Threshold</span>
              <span className="font-mono font-bold text-white">{params.normalization_threshold}</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="1.0"
              step="0.05"
              value={params.normalization_threshold}
              onChange={(e) =>
                onChangeParams({ ...params, normalization_threshold: parseFloat(e.target.value) })
              }
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-300">
              <span>Amplification Threshold</span>
              <span className="font-mono font-bold text-white">{params.amplification_threshold}</span>
            </div>
            <input
              type="range"
              min="0.2"
              max="1.0"
              step="0.05"
              value={params.amplification_threshold}
              onChange={(e) =>
                onChangeParams({ ...params, amplification_threshold: parseFloat(e.target.value) })
              }
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
            />
          </div>
        </div>

        {/* Karaoke Studio Storage & Reset */}
        <div className="space-y-3 pt-3 border-t border-slate-800">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block">
            {lang === 'tr' ? 'Karaoke & Veritabanı Yönetimi' : 'Karaoke & Database Storage'}
          </label>

          <div className={cn('p-4 rounded-2xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4', themeStyle.card)}>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Trash2 className={cn('w-4 h-4', themeStyle.icon)} />
                <span className="text-xs font-bold text-white">
                  {lang === 'tr' ? 'Tüm Çalışmaları & İndirmeleri Temizle' : 'Clear All Outputs & Downloads'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                {lang === 'tr'
                  ? 'outputs/, ytdl/ ve uploads/ klasörlerindeki tüm dosyaları (ayrıştırılmış sesler, karaoke videoları, indirmeler) ve veritabanı kayıtlarını tamamen siler.'
                  : 'Wipes all files in outputs/, ytdl/, and uploads/ (stems, karaoke videos, downloads) and SQLite database records.'}
              </p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {confirmClear ? (
                <>
                  <button
                    type="button"
                    onClick={() => setConfirmClear(false)}
                    disabled={isClearingKaraoke}
                    className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 text-xs font-bold transition-all cursor-pointer"
                  >
                    {lang === 'tr' ? 'Vazgeç' : 'Cancel'}
                  </button>
                  <button
                    type="button"
                    onClick={handleClearKaraoke}
                    disabled={isClearingKaraoke}
                    className={cn('px-3.5 py-2 rounded-xl text-white text-xs font-bold shadow-lg active:scale-95 transition-all flex items-center gap-1.5 cursor-pointer', themeStyle.confirmBtn)}
                  >
                    {isClearingKaraoke ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <AlertTriangle className="w-3.5 h-3.5" />
                    )}
                    <span>{lang === 'tr' ? 'Evet, Hepsini Sil' : 'Yes, Delete All'}</span>
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={handleClearKaraoke}
                  className={cn('px-4 py-2 rounded-xl border text-xs font-bold active:scale-95 transition-all flex items-center gap-2 cursor-pointer', themeStyle.btn)}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>{lang === 'tr' ? 'Tümünü Temizle' : 'Wipe Everything'}</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Save & Close Button */}
        <button
          onClick={() => {
            onClose();
            onNotify('success', 'Settings Saved');
          }}
          className={cn(
            'w-full py-3.5 rounded-2xl font-bold text-xs text-white shadow-xl transition-transform active:scale-95 flex items-center justify-center gap-2 cursor-pointer',
            accentColor === 'indigo' && 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-500/25',
            accentColor === 'emerald' && 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-500/25',
            accentColor === 'rose' && 'bg-rose-600 hover:bg-rose-500 shadow-rose-500/25',
            accentColor === 'amber' && 'bg-amber-600 hover:bg-amber-500 shadow-amber-500/25',
            accentColor === 'violet' && 'bg-violet-600 hover:bg-violet-500 shadow-violet-500/25'
          )}
        >
          <CheckCircle2 className="w-4 h-4" />
          <span>{t('Save & Close')}</span>
        </button>
      </div>
    </div>
  );
};
