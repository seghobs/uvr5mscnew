'use client';

import {StudioSelect} from './StudioSelect';

import React, { useState } from 'react';
import {
  FolderArchive,
  Play,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Cpu,
  Sliders,
  FolderInput,
  FolderOutput,
  Terminal,
  Sparkles,
} from 'lucide-react';
import {
  Language,
  AccentColor,
  AvailableModels,
  SeparationParams,
  BatchRequest,
} from '@/lib/types';
import { cn } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';

interface BatchProcessingViewProps {
  lang: Language;
  accentColor: AccentColor;
  availableModels: AvailableModels;
  outputFormat: string;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const BatchProcessingView: React.FC<BatchProcessingViewProps> = ({
  lang,
  accentColor,
  availableModels,
  outputFormat,
  onNotify,
}) => {
  const t = (key: string) => getTranslation(lang, key);

  const [inputDir, setInputDir] = useState<string>('');
  const [outputDir, setOutputDir] = useState<string>('outputs');
  const [modelType, setModelType] = useState<string>('roformer');
  const [modelKey, setModelKey] = useState<string>('');

  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentMessage, setCurrentMessage] = useState<string>('');
  const [logs, setLogs] = useState<string[]>([]);

  // Update default modelKey when modelType changes
  React.useEffect(() => {
    const models = availableModels[modelType] || [];
    if (models.length > 0 && !models.includes(modelKey)) {
      setModelKey(models[0]);
    }
  }, [modelType, availableModels]);

  const handleStartBatch = async () => {
    if (!inputDir.trim()) {
      onNotify('warning', 'Klasör Yolu Gerekli', 'Lütfen işlenecek seslerin bulunduğu klasör yolunu girin.');
      return;
    }

    setIsProcessing(true);
    setProgress(5);
    setCurrentMessage('Toplu işleme başlatılıyor...');
    setLogs([`[${new Date().toLocaleTimeString()}] Başlatıldı: ${inputDir} -> ${outputDir}`]);

    try {
      const payload: BatchRequest = {
        input_dir: inputDir.trim(),
        output_dir: outputDir.trim() || 'outputs',
        model_type: modelType,
        model_key: modelKey,
        out_format: outputFormat,
      };

      const res = await api.startBatch(payload);
      const taskId = res.task_id;

      const poll = setInterval(async () => {
        try {
          const st = await api.getTaskStatus(taskId);
          const raw = st.progress || 0.1;
          const pct = Math.round(raw <= 1.0 ? raw * 100 : raw);
          setProgress(Math.max(5, Math.min(100, pct)));
          if (st.message) {
            setCurrentMessage(st.message);
            setLogs((prev) => {
              if (prev[prev.length - 1] !== st.message) {
                return [...prev, `[${new Date().toLocaleTimeString()}] ${st.message}`];
              }
              return prev;
            });
          }

          if (st.status === 'completed') {
            clearInterval(poll);
            setIsProcessing(false);
            setProgress(100);
            onNotify('success', 'Toplu İşlem Tamamlandı!', `${st.message || 'Tüm dosyalar ayrıştırıldı.'}`);
          } else if (st.status === 'failed') {
            clearInterval(poll);
            setIsProcessing(false);
            onNotify('error', 'Toplu İşlem Başarısız', st.error || st.message);
          }
        } catch (err) {
          clearInterval(poll);
          setIsProcessing(false);
        }
      }, 1500);
    } catch (e: any) {
      setIsProcessing(false);
      onNotify('error', 'İşlem Başlatılamadı', e.message || 'Klasör yolu bulunamadı');
    }
  };

  const modelsForType = availableModels[modelType] || [];

  return (
    <div className="glass-panel rounded-3xl p-6 sm:p-8 lg:p-8 shadow-2xl space-y-6 border border-white/10">
      {/* Header */}
      <div className="flex items-center gap-3.5">
        <div className="p-3 rounded-2xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 shadow-[0_0_15px_rgba(99,102,241,0.2)]">
          <FolderArchive className="w-6 h-6" />
        </div>
        <div>
          <h3 className="text-xl font-black font-outfit text-white tracking-tight">
            Toplu Klasör Ayrıştırma (Batch Processing)
          </h3>
          <p className="text-xs text-slate-400">
            Bilgisayarınızdaki bir klasördeki tüm ses dosyalarını tek tıkla arka arkaya otomatik ayrıştırın.
          </p>
        </div>
      </div>

      {/* Directory Paths Input Form */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Input Directory */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-slate-300 flex items-center gap-2">
            <FolderInput className="w-4 h-4 text-indigo-400" />
            Girdi Klasörü Yolu (Input Directory)
          </label>
          <input
            type="text"
            value={inputDir}
            onChange={(e) => setInputDir(e.target.value)}
            placeholder="Örn: C:\Users\user\Music veya D:\Album"
            className="w-full px-4 py-3 rounded-2xl bg-slate-950/80 border border-white/10 text-white placeholder-slate-500 text-xs sm:text-sm outline-none focus:border-indigo-500/50 transition-colors"
          />
        </div>

        {/* Output Directory */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-slate-300 flex items-center gap-2">
            <FolderOutput className="w-4 h-4 text-emerald-400" />
            Çıktı Klasörü (Output Directory)
          </label>
          <input
            type="text"
            value={outputDir}
            onChange={(e) => setOutputDir(e.target.value)}
            placeholder="outputs"
            className="w-full px-4 py-3 rounded-2xl bg-slate-950/80 border border-white/10 text-white placeholder-slate-500 text-xs sm:text-sm outline-none focus:border-emerald-500/50 transition-colors"
          />
        </div>
      </div>

      {/* Model Selection for Batch */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-5 rounded-2xl glass-panel border border-white/10 bg-slate-900/50">
        {/* Model Architecture */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Model Mimarisi
          </label>
          <StudioSelect
            aria-label="Model Mimarisi"
            value={modelType}
            onValueChange={(value) => setModelType(value)}
            className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-white/10 text-white text-xs font-bold outline-none cursor-pointer"
          >
            <option value="roformer">BS / Mel Roformer</option>
            <option value="mdx23c">MDX23C</option>
            <option value="mdxnet">MDX-NET</option>
            <option value="vrarch">VR Arch</option>
            <option value="demucs">Demucs v4</option>
          </StudioSelect>
        </div>

        {/* Model Key */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Kullanılacak Model
          </label>
          <StudioSelect
            aria-label="Kullanılacak Model"
            value={modelKey}
            onValueChange={(value) => setModelKey(value)}
            className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-white/10 text-white text-xs font-bold outline-none cursor-pointer"
          >
            {modelsForType.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </StudioSelect>
        </div>
      </div>

      {/* Progress Bar when Active */}
      {isProcessing && (
        <div className="p-5 rounded-2xl glass-panel border border-indigo-500/30 bg-slate-950/80 space-y-3 animate-in fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
              <span className="text-xs font-bold text-white">{currentMessage}</span>
            </div>
            <span className="text-sm font-mono font-bold text-indigo-400">%{progress}</span>
          </div>

          <div className="w-full bg-slate-900 h-3 rounded-full overflow-hidden border border-white/10 p-0.5">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-indigo-600 rounded-full transition-all duration-300 shadow-[0_0_15px_rgba(99,102,241,0.5)]"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Live Terminal Log */}
      {logs.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-wider">
            <Terminal className="w-4 h-4 text-slate-400" />
            İşlem Günlüğü (Console Log)
          </div>
          <div className="p-4 rounded-2xl bg-black/80 border border-white/10 font-mono text-xs text-emerald-400 max-h-40 overflow-y-auto custom-scrollbar space-y-1">
            {logs.map((log, i) => (
              <div key={i}>{log}</div>
            ))}
          </div>
        </div>
      )}

      {/* Action Button */}
      <button
        onClick={handleStartBatch}
        disabled={isProcessing || !inputDir.trim()}
        className={cn(
          'w-full py-4 rounded-2xl text-sm font-black font-outfit text-white transition-all flex items-center justify-center gap-2.5 shadow-xl active:scale-[0.99] disabled:opacity-50',
          accentColor === 'indigo' && 'bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 shadow-indigo-500/25',
          accentColor === 'emerald' && 'bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 shadow-emerald-500/25',
          accentColor === 'rose' && 'bg-gradient-to-r from-rose-600 to-rose-700 hover:from-rose-500 hover:to-rose-600 shadow-rose-500/25',
          accentColor === 'amber' && 'bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-500 hover:to-amber-600 shadow-amber-500/25',
          accentColor === 'violet' && 'bg-gradient-to-r from-violet-600 to-violet-700 hover:from-violet-500 hover:to-violet-600 shadow-violet-500/25'
        )}
      >
        {isProcessing ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Toplu İşlem Devam Ediyor...</span>
          </>
        ) : (
          <>
            <Play className="w-5 h-5 fill-white" />
            <span>Toplu Klasör Ayrıştırmayı Başlat</span>
          </>
        )}
      </button>
    </div>
  );
};
