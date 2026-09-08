'use client';

import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Sparkles,
  X,
  Loader2,
  ShieldCheck,
  Zap,
  Sliders,
  CheckCircle2,
  Volume2,
  ArrowRight,
  Download,
  ArrowRightLeft,
} from 'lucide-react';
import { Language } from '@/lib/types';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { ABCompareModal } from './ABCompareModal';

interface RestoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  stem: string;
  lang: Language;
  onNewStemCreated?: (filename: string) => void;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const RestoreModal: React.FC<RestoreModalProps> = ({
  isOpen,
  onClose,
  stem,
  lang,
  onNewStemCreated,
  onNotify,
}) => {
  const [denoise, setDenoise] = useState(true);
  const [enhanceSr, setEnhanceSr] = useState(true);
  const [ddimSteps, setDdimSteps] = useState(20);
  const [guidanceScale, setGuidanceScale] = useState(3.5);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [completedFile, setCompletedFile] = useState<string | null>(null);
  const [showABModal, setShowABModal] = useState(false);

  if (!isOpen) return null;

  const handleStartRestore = async () => {
    if (!denoise && !enhanceSr) {
      onNotify('warning', 'Mod Seçimi Gerekli', 'Lütfen en az bir restorasyon aşamasını (Gürültü Kazıma veya AudioSR) seçin.');
      return;
    }

    setIsProcessing(true);
    setProgress(5);
    setProgressMessage('Restorasyon motoru hazırlanıyor...');
    setCompletedFile(null);

    try {
      const res = await api.restoreAudio(
        {
          file_name: stem,
          denoise,
          enhance_sr: enhanceSr,
          ddim_steps: ddimSteps,
          guidance_scale: guidanceScale,
        },
        (msg, p) => {
          setProgressMessage(msg);
          setProgress(p);
        }
      );

      if (res && res.output_file) {
        setCompletedFile(res.output_file);
        setProgress(100);
        setProgressMessage('Restorasyon başarıyla tamamlandı!');
        onNotify('success', 'Restorasyon Tamamlandı', `${res.output_file} stüdyo oynatıcısına eklendi.`);
        if (onNewStemCreated) {
          onNewStemCreated(res.output_file);
        }
      }
    } catch (err: any) {
      onNotify('error', 'Restorasyon Hatası', err.message || 'Bilinmeyen hata');
    } finally {
      setIsProcessing(false);
    }
  };

  const modalContent = (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl shadow-indigo-950/50 flex flex-col overflow-hidden text-slate-200">
        
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-300 shadow-md shadow-cyan-500/10">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base sm:text-lg text-white flex items-center gap-2">
                <span>AI Restorasyon & Parlatma</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  48kHz Hi-Fi
                </span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Roformer Denoise (28dB) + AudioSR Difüzyon Motoru
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-40"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
          {/* Target Track Card */}
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80 flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              <Volume2 className="w-4 h-4 text-slate-400 shrink-0" />
              <div className="min-w-0">
                <span className="text-[11px] text-slate-400 block font-medium">Onarılacak Ses Kanalı</span>
                <span className="text-xs font-mono font-bold text-white truncate block">{stem}</span>
              </div>
            </div>
            <span className="text-[10px] font-mono px-2 py-1 rounded bg-slate-800 text-slate-300 shrink-0">
              RTX 5060 Hızlandırmalı
            </span>
          </div>

          {/* Quick Preset Buttons */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <span>Hızlı Profil Seçimi</span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => { setDenoise(true); setEnhanceSr(true); }}
                className={cn(
                  "p-3 rounded-xl border text-left transition-all flex flex-col justify-between gap-1",
                  denoise && enhanceSr
                    ? "bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 border-cyan-500/50 shadow-md shadow-cyan-500/10 text-white"
                    : "bg-slate-950/40 border-slate-800 text-slate-400 hover:bg-slate-800/60"
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-cyan-300">✨ Tam Restorasyon</span>
                  {denoise && enhanceSr && <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />}
                </div>
                <span className="text-[10px] text-slate-400 leading-tight">
                  Denoise (28dB) + 48kHz AudioSR. Boğuk kayıtlar için önerilir.
                </span>
              </button>

              <button
                type="button"
                onClick={() => { setDenoise(true); setEnhanceSr(false); }}
                className={cn(
                  "p-3 rounded-xl border text-left transition-all flex flex-col justify-between gap-1",
                  denoise && !enhanceSr
                    ? "bg-sky-500/20 border-sky-500/50 shadow-md text-white"
                    : "bg-slate-950/40 border-slate-800 text-slate-400 hover:bg-slate-800/60"
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-sky-300">🛡️ Yalnızca Denoise</span>
                  {denoise && !enhanceSr && <CheckCircle2 className="w-3.5 h-3.5 text-sky-400" />}
                </div>
                <span className="text-[10px] text-slate-400 leading-tight">
                  Kaset hışırtısı, amfi vızıltısı ve dip gürültüyü kazır.
                </span>
              </button>

              <button
                type="button"
                onClick={() => { setDenoise(false); setEnhanceSr(true); }}
                className={cn(
                  "p-3 rounded-xl border text-left transition-all flex flex-col justify-between gap-1",
                  !denoise && enhanceSr
                    ? "bg-violet-500/20 border-violet-500/50 shadow-md text-white"
                    : "bg-slate-950/40 border-slate-800 text-slate-400 hover:bg-slate-800/60"
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-violet-300">⚡ Yalnızca AudioSR</span>
                  {!denoise && enhanceSr && <CheckCircle2 className="w-3.5 h-3.5 text-violet-400" />}
                </div>
                <span className="text-[10px] text-slate-400 leading-tight">
                  Dip gürültüsü olmayan temiz ama boğuk sesleri parlatır.
                </span>
              </button>
            </div>
          </div>

          {/* 2 Stages Detailed Toggles */}
          <div className="space-y-2 pt-1">
            <div
              onClick={() => setDenoise(!denoise)}
              className={cn(
                "p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between",
                denoise
                  ? "bg-sky-950/40 border-sky-500/40 text-sky-200"
                  : "bg-slate-950/20 border-slate-800 text-slate-500"
              )}
            >
              <div className="flex items-center gap-3">
                <div className={cn("p-2 rounded-lg", denoise ? "bg-sky-500/20 text-sky-300" : "bg-slate-800 text-slate-500")}>
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold flex items-center gap-2">
                    <span>Aşama 1: Mel-Roformer Denoise (Aufr33 SDR 27.99 dB)</span>
                    {denoise && <span className="text-[9px] px-1.5 py-0.5 rounded bg-sky-500/30 text-sky-200">Aktif</span>}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Dip gürültü, kaset hışırtısı, fan sesi ve amfi vızıltılarını müzikten ayıklar.
                  </p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={denoise}
                onChange={() => {}}
                className="rounded border-slate-700 bg-slate-900 text-sky-500 focus:ring-0 cursor-pointer"
              />
            </div>

            <div
              onClick={() => setEnhanceSr(!enhanceSr)}
              className={cn(
                "p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between",
                enhanceSr
                  ? "bg-cyan-950/40 border-cyan-500/40 text-cyan-200"
                  : "bg-slate-950/20 border-slate-800 text-slate-500"
              )}
            >
              <div className="flex items-center gap-3">
                <div className={cn("p-2 rounded-lg", enhanceSr ? "bg-cyan-500/20 text-cyan-300" : "bg-slate-800 text-slate-500")}>
                  <Zap className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold flex items-center gap-2">
                    <span>Aşama 2: AudioSR 48kHz Super-Resolution (Difüzyon)</span>
                    {enhanceSr && <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/30 text-cyan-200">Aktif</span>}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Kayıp 16kHz-24kHz harmonikleri baştan üreterek kristal stüdyo parlaklığı verir.
                  </p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={enhanceSr}
                onChange={() => {}}
                className="rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-0 cursor-pointer"
              />
            </div>
          </div>

          {/* Advanced Settings Accordion */}
          {enhanceSr && (
            <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/40">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="w-full px-3.5 py-2.5 flex items-center justify-between text-xs font-semibold text-slate-400 hover:text-slate-200 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-cyan-400" />
                  Gelişmiş Difüzyon Ayarları
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {showAdvanced ? 'Gizle ▲' : 'Göster ▼'}
                </span>
              </button>

              {showAdvanced && (
                <div className="p-3.5 pt-1 space-y-3 border-t border-slate-800/80">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-300">DDIM Kalite Adımları (Steps)</span>
                      <span className="font-mono text-cyan-400 font-bold">{ddimSteps} adım</span>
                    </div>
                    <input
                      type="range"
                      min={10}
                      max={50}
                      step={5}
                      value={ddimSteps}
                      onChange={(e) => setDdimSteps(parseInt(e.target.value))}
                      className="w-full accent-cyan-500 cursor-pointer"
                    />
                    <span className="text-[10px] text-slate-500 block mt-0.5">
                      20 adım RTX 5060 için optimum stüdyo hızı ve yüksek kalite sunar.
                    </span>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-300">Yeniden Yapılandırma Gücü (Guidance Scale)</span>
                      <span className="font-mono text-cyan-400 font-bold">{guidanceScale.toFixed(1)}</span>
                    </div>
                    <input
                      type="range"
                      min={1.0}
                      max={5.0}
                      step={0.5}
                      value={guidanceScale}
                      onChange={(e) => setGuidanceScale(parseFloat(e.target.value))}
                      className="w-full accent-cyan-500 cursor-pointer"
                    />
                    <span className="text-[10px] text-slate-500 block mt-0.5">
                      Değer arttıkça orijinal ses karakterine sadık kalarak tizleri açar (Varsayılan: 3.5).
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Real-time Progress Bar */}
          {isProcessing && (
            <div className="p-4 rounded-xl bg-slate-950 border border-cyan-500/30 space-y-2 animate-in fade-in">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-cyan-300 flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  {progressMessage || 'İşleniyor...'}
                </span>
                <span className="font-mono font-bold text-cyan-400">%{progress}</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 via-cyan-400 to-emerald-400 transition-all duration-300 rounded-full"
                  style={{ width: `${Math.max(5, Math.min(100, progress))}%` }}
                />
              </div>
            </div>
          )}

          {/* Success Card */}
          {completedFile && !isProcessing && (
            <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-200 space-y-2 animate-in fade-in">
              <div className="flex items-center gap-2 font-bold text-xs">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Restorasyon Başarıyla Tamamlandı!</span>
              </div>
              <p className="text-xs text-slate-300 font-mono truncate">
                {completedFile}
              </p>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowABModal(true)}
                  className="px-3.5 py-2 rounded-xl bg-gradient-to-r from-amber-500/25 via-cyan-500/25 to-indigo-500/25 hover:from-amber-500/35 hover:to-cyan-500/35 text-white font-bold text-xs border border-cyan-500/40 flex items-center gap-1.5 transition-all shadow-md shadow-cyan-500/10 active:scale-95"
                >
                  <ArrowRightLeft className="w-3.5 h-3.5 text-cyan-300" />
                  <span>🔀 Kalite Farkını Karşılaştır (A/B Testi)</span>
                </button>
                <a
                  href={`/output/${encodeURIComponent(completedFile)}`}
                  download={completedFile}
                  className="px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-md shadow-emerald-600/20"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>İndir</span>
                </a>
              </div>
              <p className="text-[11px] text-emerald-400">
                ✓ 48kHz Hi-Fi restorasyon oynatıcıya eklendi. Yukarıdaki butona tıklayarak orijinal ses ile anlık A/B kıyaslaması yapabilirsiniz.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-end gap-2.5">
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 transition-colors disabled:opacity-40"
          >
            {completedFile ? 'Kapat' : 'Vazgeç'}
          </button>
          
          {!completedFile ? (
            <button
              type="button"
              onClick={handleStartRestore}
              disabled={isProcessing}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 via-cyan-600 to-teal-500 hover:from-indigo-500 hover:to-teal-400 text-white text-xs font-bold transition-all shadow-lg shadow-cyan-600/25 flex items-center gap-2 active:scale-95 disabled:opacity-50"
            >
              {isProcessing ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>İşleniyor (%{progress})...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-cyan-200" />
                  <span>Restorasyonu Başlat</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => { setCompletedFile(null); setProgress(0); }}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold transition-all"
            >
              Yeni Restorasyon Yap
            </button>
          )}
        </div>

      </div>

      {/* A/B Quality Comparison Modal */}
      {completedFile && (
        <ABCompareModal
          isOpen={showABModal}
          onClose={() => setShowABModal(false)}
          originalFile={stem}
          restoredFile={completedFile}
          lang={lang}
        />
      )}
    </div>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(modalContent, document.body);
};
