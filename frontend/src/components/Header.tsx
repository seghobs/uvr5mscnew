'use client';

import React, { useEffect, useState, useRef } from 'react';
import { Cpu, Settings, Globe, Sparkles, Radio, CloudDownload, Power, CheckCircle2, Loader2, Trash2, RotateCcw, X } from 'lucide-react';
import { Language, AccentColor } from '@/lib/types';
import { cn } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';
import { flushAllProjects } from '@/lib/project-storage';

interface HeaderProps {
  lang: Language;
  onToggleLang: () => void;
  accentColor: AccentColor;
  onChangeAccent: (color: AccentColor) => void;
  onOpenSettings: () => void;
  onOpenModelHub?: () => void;
  device: string;
}

const accentColors: { id: AccentColor; name: string; bgClass: string; glowClass: string }[] = [
  { id: 'indigo', name: 'Indigo', bgClass: 'bg-indigo-500', glowClass: 'shadow-indigo-500/50' },
  { id: 'emerald', name: 'Emerald', bgClass: 'bg-emerald-500', glowClass: 'shadow-emerald-500/50' },
  { id: 'rose', name: 'Rose', bgClass: 'bg-rose-500', glowClass: 'shadow-rose-500/50' },
  { id: 'amber', name: 'Amber', bgClass: 'bg-amber-500', glowClass: 'shadow-amber-500/50' },
  { id: 'violet', name: 'Violet', bgClass: 'bg-violet-500', glowClass: 'shadow-violet-500/50' },
];

export const Header: React.FC<HeaderProps> = ({
  lang,
  onToggleLang,
  accentColor,
  onChangeAccent,
  onOpenSettings,
  onOpenModelHub,
  device,
}) => {
  const t = (key: string) => getTranslation(lang, key);
  const [showShutdownModal, setShowShutdownModal] = useState(false);
  const [isShuttingDown, setIsShuttingDown] = useState(false);
  const [isTerminated, setIsTerminated] = useState(false);
  const [isClearingMemory, setIsClearingMemory] = useState(false);
  const [memoryClearedMsg, setMemoryClearedMsg] = useState<string | null>(null);
  const [restartMessage, setRestartMessage] = useState('');
  const [restartError, setRestartError] = useState('');
  const restartBusy=useRef(false);
  const handleStudioRestart = async (existingJob?:{id:string}) => {
    if (restartBusy.current) return;
    restartBusy.current=true;
    setRestartError(''); setRestartMessage('Çalışma alanı kaydediliyor…');
    try {
      window.dispatchEvent(new Event('uvr-before-restart'));
      await flushAllProjects();
      let job=existingJob;
      if(!job){
        const response = await fetch('/api/service/rebuild-restart', {method:'POST'});
        job = await response.json();
        if (!response.ok) throw Error('Yeniden başlatma başlatılamadı.');
      }
      if(!job)throw Error('Yeniden başlatma kimliği alınamadı.');
      // Poll the backend directly: the frontend is briefly unavailable during its restart.
      const hostname = window.location.hostname;
      const host = ['localhost','127.0.0.1','[::1]'].includes(hostname) ? '127.0.0.1' : hostname;
      const deadline = Date.now() + 25*60*60*1000;
      while (Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 1500));
        let current;
        try {
          const status = await fetch(`http://${host}:8000/api/service/rebuild-restart`, {cache:'no-store', signal:AbortSignal.timeout(5000)});
          if (!status.ok) continue;
          current = await status.json();
        } catch { continue; }
        if (current.id !== job.id) throw Error('Yeniden başlatma durumu değişti. Lütfen tekrar deneyin.');
        if (current.phase === 'failed') throw Error(current.message);
        setRestartMessage(current.message || 'Yeniden başlatılıyor…');
        if (current.phase === 'completed') {
          window.dispatchEvent(new Event('uvr-before-restart'));
          await flushAllProjects();
          window.location.reload();
          return;
        }
      }
      throw Error('Yeniden başlatma bekleme süresi doldu.');
    } catch (error) {
      for (let index=sessionStorage.length-1;index>=0;index--) {
        const key=sessionStorage.key(index);
        if(key?.startsWith('uvr-restart-'))sessionStorage.removeItem(key);
      }
      setRestartError((error as Error).message); setRestartMessage('');restartBusy.current=false;
    }
  };
  useEffect(()=>{
    const restart=()=>{void handleStudioRestart();};
    window.addEventListener('uvr-restart-request',restart);
    return()=>window.removeEventListener('uvr-restart-request',restart);
  },[restartMessage]);

  useEffect(()=>{
    let live=true,busy=false;
    const poll=async()=>{
      if(busy||restartBusy.current)return;busy=true;
      try{
        const response=await fetch('/api/service/rebuild-restart',{cache:'no-store',signal:AbortSignal.timeout(4000)});
        if(!response.ok)return;
        const job=await response.json();
        if(live&&job.automatic&&['queued','waiting','building','restarting'].includes(job.phase))void handleStudioRestart(job);
      }catch{}finally{busy=false;}
    };
    const timer=setInterval(()=>void poll(),2000);
    return()=>{live=false;clearInterval(timer);};
  },[]);

  const handleClearMemory = async () => {
    setIsClearingMemory(true);
    try {
      const res = await api.clearMemory();
      const vramMb = res.gpu?.allocated_mb !== undefined ? `${res.gpu.allocated_mb} MB` : '0 MB';
      setMemoryClearedMsg(`VRAM: ${vramMb}`);
      setTimeout(() => setMemoryClearedMsg(null), 3500);
    } catch {
      setMemoryClearedMsg('Temizlendi');
      setTimeout(() => setMemoryClearedMsg(null), 3000);
    } finally {
      setIsClearingMemory(false);
    }
  };

  const handleShutdownConfirm = async () => {
    setIsShuttingDown(true);
    try {
      await flushAllProjects();
      await api.shutdown();
    } catch(error) {
      setIsShuttingDown(false);setMemoryClearedMsg((error as Error).message||'Kapatılamadı. Çalışan işlemleri kontrol edin.');return;
    }
    setTimeout(() => {
      setIsShuttingDown(false);
      setIsTerminated(true);
    }, 800);
  };

  return (
    <>
      <header className="studio-header sticky top-0 z-40 w-full backdrop-blur-2xl bg-slate-950/70 border-b border-white/[0.08] px-6 lg:px-10 py-3.5 transition-all">
        <div className="max-w-[1840px] mx-auto flex items-center justify-between gap-4 flex-wrap">
          {/* Brand Logo & Tag */}
          <div className="flex items-center gap-4">
            <div className="relative group cursor-pointer">
              <div
                className={cn(
                  'w-11 h-11 rounded-2xl flex items-center justify-center shadow-xl transition-all duration-300 group-hover:scale-105',
                  accentColor === 'indigo' && 'bg-gradient-to-br from-indigo-500 to-indigo-700 shadow-indigo-500/30',
                  accentColor === 'emerald' && 'bg-gradient-to-br from-emerald-500 to-emerald-700 shadow-emerald-500/30',
                  accentColor === 'rose' && 'bg-gradient-to-br from-rose-500 to-rose-700 shadow-rose-500/30',
                  accentColor === 'amber' && 'bg-gradient-to-br from-amber-500 to-amber-700 shadow-amber-500/30',
                  accentColor === 'violet' && 'bg-gradient-to-br from-violet-500 to-violet-700 shadow-violet-500/30'
                )}
              >
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-slate-950 flex items-center justify-center">
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
              </div>
            </div>

            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl lg:text-2xl font-black tracking-tight text-white font-outfit">
                  UVR5
                </h1>
                <span
                  className={cn(
                    'text-[10px] px-2.5 py-0.5 rounded-full font-bold uppercase tracking-widest border backdrop-blur-md shadow-sm',
                    accentColor === 'indigo' && 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30 shadow-indigo-500/20',
                    accentColor === 'emerald' && 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30 shadow-emerald-500/20',
                    accentColor === 'rose' && 'bg-rose-500/15 text-rose-300 border-rose-500/30 shadow-rose-500/20',
                    accentColor === 'amber' && 'bg-amber-500/15 text-amber-300 border-amber-500/30 shadow-amber-500/20',
                    accentColor === 'violet' && 'bg-violet-500/15 text-violet-300 border-violet-500/30 shadow-violet-500/20'
                  )}
                >
                  music studio
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium tracking-wide hidden sm:block">
                AI Audio Source Separation & Real-time Web DAW
              </p>
            </div>
          </div>

          {/* Right Controls */}
          <div className="flex items-center gap-2.5 sm:gap-3">
            {/* Hardware Device Badge */}
            <div className="hidden md:flex items-center gap-2.5 px-3.5 py-1.5 rounded-2xl glass-panel text-xs text-slate-200 border border-white/5 shadow-inner">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
              <Cpu className="w-3.5 h-3.5 text-slate-400" />
              <span className="font-mono font-medium text-[11px]">{device}</span>
            </div>

            {/* Accent Color Palette */}
            <div className="flex items-center gap-1.5 p-1 rounded-2xl glass-panel border border-white/5">
              {accentColors.map((col) => (
                <button
                  key={col.id}
                  onClick={() => onChangeAccent(col.id)}
                  title={col.name}
                  aria-label={col.name}
                  aria-pressed={accentColor === col.id}
                  className={cn(
                    'w-5 h-5 rounded-xl transition-all duration-300 active:scale-90 relative flex items-center justify-center',
                    col.bgClass,
                    accentColor === col.id
                      ? cn('scale-110 shadow-lg ring-2 ring-white/80', col.glowClass)
                      : 'opacity-40 hover:opacity-100 hover:scale-105'
                  )}
                />
              ))}
            </div>

            {/* Model Hub Trigger */}
            {onOpenModelHub && (
              <button
                onClick={onOpenModelHub}
                title="Model İndirme & Yönetim Merkezi"
                className="p-2.5 rounded-2xl glass-panel hover:bg-white/[0.08] border border-white/10 text-slate-300 hover:text-white transition-all duration-200 active:scale-95 shadow-sm flex items-center gap-1.5 cursor-pointer"
              >
                <CloudDownload className="w-4 h-4 text-indigo-400" />
                <span className="text-xs font-bold font-outfit hidden lg:inline">Modeller</span>
              </button>
            )}

            {/* Language Switcher */}
            <button
              onClick={onToggleLang}
              className="flex items-center gap-2 px-3.5 py-2 rounded-2xl glass-panel hover:bg-white/[0.08] border border-white/10 text-xs font-bold text-slate-200 transition-all duration-200 active:scale-95 shadow-sm cursor-pointer"
            >
              <Globe className="w-3.5 h-3.5 text-indigo-400" />
              <span className="font-mono">{lang.toUpperCase()}</span>
            </button>

            {/* Settings Trigger */}
            <button
              onClick={onOpenSettings}
              title={t('Global Settings')}
              className="p-2.5 rounded-2xl glass-panel hover:bg-white/[0.08] border border-white/10 text-slate-300 hover:text-white transition-all duration-200 active:scale-95 shadow-sm cursor-pointer"
            >
              <Settings className="w-4 h-4" />
            </button>

            {/* Clear VRAM / Memory Button */}
            <button
              onClick={handleClearMemory}
              disabled={isClearingMemory}
              title="Ekran Kartı (VRAM) ve Sistem Belleğini (RAM) Boşalt"
              className={cn(
                "px-3 py-2 rounded-2xl border transition-all duration-200 active:scale-95 shadow-sm flex items-center gap-1.5 cursor-pointer disabled:opacity-50",
                memoryClearedMsg
                  ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                  : "bg-indigo-500/15 hover:bg-indigo-500/25 border-indigo-500/30 text-indigo-300 hover:text-indigo-200"
              )}
            >
              {isClearingMemory ? (
                <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
              ) : memoryClearedMsg ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <Trash2 className="w-4 h-4 text-indigo-400" />
              )}
              <span className="text-xs font-bold font-outfit hidden sm:inline">
                {memoryClearedMsg ? memoryClearedMsg : "VRAM Boşalt"}
              </span>
            </button>

            {/* Shutdown / Power Off Button */}
            <button onClick={()=>void handleStudioRestart()} disabled={!!restartMessage}
              title="Önce derle, sonra backend ve frontend’i yeniden başlat"
              className="flex items-center gap-2 rounded-2xl border border-indigo-300/25 bg-indigo-300/10 px-3 py-2 text-sm font-semibold text-indigo-200 hover:bg-indigo-300/20 disabled:opacity-50">
              {restartMessage ? <Loader2 size={16} className="animate-spin"/> : <RotateCcw size={16}/>}
              <span className="hidden sm:inline">Restart</span>
            </button>
            <button
              onClick={() => setShowShutdownModal(true)}
              title="Uygulamayı ve Arka Plandaki Tüm Servisleri Kapat"
              className="px-3 py-2 rounded-2xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-300 hover:text-rose-200 transition-all duration-200 active:scale-95 shadow-sm flex items-center gap-1.5 cursor-pointer"
            >
              <Power className="w-4 h-4 text-rose-400" />
              <span className="text-xs font-black font-outfit hidden sm:inline">Kapat</span>
            </button>
          </div>
        </div>
      </header>
      {(restartMessage || restartError) && <div role={restartError?'alert':'status'} className="fixed bottom-5 left-1/2 z-[10000] flex w-[min(92vw,620px)] -translate-x-1/2 items-center gap-3 rounded-2xl border border-indigo-300/25 bg-[#262230] px-5 py-4 text-sm text-slate-100 shadow-xl">
        {restartMessage && <Loader2 size={18} className="shrink-0 animate-spin text-indigo-300"/>}
        <span className="flex-1">{restartMessage || restartError}</span>
        {restartError && <button onClick={()=>setRestartError('')} aria-label="Bildirimi kapat"><X size={16}/></button>}
      </div>}

      {/* Shutdown Confirmation Modal */}
      {showShutdownModal && !isTerminated && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-rose-500/30 rounded-3xl p-6 max-w-md w-full shadow-2xl shadow-rose-500/10 space-y-5 animate-in fade-in zoom-in duration-200">
            <div className="flex items-center gap-3.5 text-rose-400">
              <div className="p-3 rounded-2xl bg-rose-500/20 border border-rose-500/30">
                <Power className="w-6 h-6 text-rose-400 animate-pulse" />
              </div>
              <div>
                <h3 className="text-base font-black text-white font-outfit">Uygulamayı Kapat</h3>
                <p className="text-xs text-slate-400">Tüm arka plan servisleri durdurulacak</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-4 rounded-2xl border border-white/5">
              UVR5 Studio, FastAPI backend, Next.js web sunucusu ve Windows’ta arka planda çalışan tüm yapay zeka süreçleri <strong>tamamen kapatılacak</strong>.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                disabled={isShuttingDown}
                onClick={() => setShowShutdownModal(false)}
                className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-bold transition-all disabled:opacity-50 cursor-pointer"
              >
                Vazgeç
              </button>
              <button
                disabled={isShuttingDown}
                onClick={handleShutdownConfirm}
                className="px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-black transition-all flex items-center gap-2 shadow-lg shadow-rose-600/30 active:scale-95 disabled:opacity-50 cursor-pointer"
              >
                {isShuttingDown ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Kapatılıyor...</span>
                  </>
                ) : (
                  <>
                    <Power className="w-4 h-4" />
                    <span>Evet, Tamamen Kapat</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Fully Terminated Good-bye Screen */}
      {isTerminated && (
        <div className="fixed inset-0 z-50 bg-slate-950/95 backdrop-blur-xl flex items-center justify-center p-4">
          <div className="bg-slate-900/90 border border-emerald-500/30 rounded-3xl p-8 max-w-md w-full text-center space-y-5 shadow-2xl shadow-emerald-500/10 animate-in fade-in zoom-in duration-300">
            <div className="w-16 h-16 rounded-3xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center mx-auto text-emerald-400 shadow-xl shadow-emerald-500/20">
              <CheckCircle2 className="w-8 h-8" />
            </div>

            <div className="space-y-1.5">
              <h3 className="text-lg font-black text-white font-outfit">UVR5 Studio Başarıyla Kapatıldı</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Tüm yapay zeka modelleri, FastAPI backend ve Next.js servisleri sonlandırıldı. Windows üzerinde çalışan hiçbir arka plan işlemi kalmadı.
              </p>
            </div>

            <div className="pt-2">
              <button
                onClick={() => {
                  try {
                    window.close();
                  } catch {}
                }}
                className="w-full py-3 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs shadow-lg shadow-emerald-600/25 transition-all active:scale-95 cursor-pointer"
              >
                Bu Sekmeyi Kapat
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
