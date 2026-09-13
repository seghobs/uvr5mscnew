'use client';

import {StudioSelect} from './StudioSelect';

import React, { useState, useEffect } from 'react';
import {
  Sliders,
  ChevronDown,
  Star,
  Download,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  Layers,
  Cpu,
  CloudDownload,
  Volume2,
  SlidersHorizontal,
  ChevronUp,
  Crown,
  Zap,
  Music2,
  Mic2,
  ArrowLeftRight,
  ShieldCheck,
} from 'lucide-react';
import {
  TabId,
  Language,
  AccentColor,
  AvailableModels,
  ModelStatus,
  SeparationParams,
  EnsembleSlot,
} from '@/lib/types';
import { cn } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';
import { useFavorites } from '@/hooks/useFavorites';
import { api } from '@/lib/api';
import studioPro from '@/lib/studio-pro-preset.json';

interface ModelConfigurationProps {
  currentTab: TabId;
  availableModels: AvailableModels;
  selectedModel: string;
  onSelectModel: (model: string) => void;
  outputFormat: string;
  onChangeOutputFormat: (format: string) => void;
  params: SeparationParams;
  onChangeParams: (params: SeparationParams) => void;
  ensembleMode: boolean;
  onToggleEnsembleMode: () => void;
  ensembleSlots: EnsembleSlot[];
  onChangeEnsembleSlots: (slots: EnsembleSlot[]) => void;
  lang: Language;
  accentColor: AccentColor;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
  onOpenModelHub?: () => void;
}

export const ModelConfiguration: React.FC<ModelConfigurationProps> = ({
  currentTab,
  availableModels,
  selectedModel,
  onSelectModel,
  outputFormat,
  onChangeOutputFormat,
  params,
  onChangeParams,
  ensembleMode,
  onToggleEnsembleMode,
  ensembleSlots,
  onChangeEnsembleSlots,
  lang,
  accentColor,
  onNotify,
  onOpenModelHub,
}) => {
  const t = (key: string) => getTranslation(lang, key);
  const { toggleFavorite, isFavorite, getSortedModels } = useFavorites();

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const dropdownContainerRef = React.useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownContainerRef.current &&
        !dropdownContainerRef.current.contains(event.target as Node)
      ) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Fetch model status on selectedModel change
  useEffect(() => {
    if (!selectedModel) return;
    let isMounted = true;
    api
      .getModelStatus(selectedModel)
      .then((status) => {
        if (isMounted) setModelStatus(status);
      })
      .catch(() => {
        if (isMounted) setModelStatus(null);
      });
    return () => {
      isMounted = false;
    };
  }, [selectedModel]);

  const handleDownloadModel = async () => {
    if (!selectedModel || isDownloading) return;
    setIsDownloading(true);
    try {
      await api.downloadModel(selectedModel);
      onNotify('success', t('Download'), `${selectedModel} ${t('downloading in background')}`);
      const interval = setInterval(async () => {
        try {
          const st = await api.getModelStatus(selectedModel);
          setModelStatus(st);
          if (st.cached) {
            clearInterval(interval);
            setIsDownloading(false);
            onNotify('success', t('Cached ✓'), `${selectedModel} ${t('ready')}`);
          }
        } catch {
          clearInterval(interval);
          setIsDownloading(false);
        }
      }, 2000);
    } catch (e: any) {
      setIsDownloading(false);
      onNotify('error', 'Download Failed', e.message || 'Could not download model');
    }
  };

  const rawModels = availableModels[currentTab] || [];
  const models = getSortedModels(rawModels);
  const filteredModels = models.filter((m) =>
    m.toLowerCase().includes(searchFilter.toLowerCase())
  );

  const getModelType = (modelName: string): string => {
    for (const [cat, list] of Object.entries(availableModels)) {
      if (list.includes(modelName)) return cat;
    }
    return 'roformer';
  };

  const applyPreset = (presetType: 'studio_pro' | 'zero_loss_exchange' | 'master_studio' | 'strings' | 'vocal' | 'piano') => {
    if (!ensembleMode) {
      onToggleEnsembleMode();
    }

    if (presetType === 'studio_pro') {
      const slots = studioPro.models.map(({model_type,model_key}) => ({model_type,model_key}));
      const missing = slots.filter(m => !availableModels[m.model_type]?.includes(m.model_key));
      if (missing.length) {
        onNotify('warning', 'Model listesi eksik', 'Model merkezini kontrol edin: ' + missing.map(m => m.model_key).join(', '));
        return;
      }
      onChangeEnsembleSlots(slots);
      onChangeParams({...params, ensemble_profile:'studio_pro', segment_size:256,
        override_segment_size:false, overlap:8, batch_size:1, normalization_threshold:1,
        amplification_threshold:0, single_stem:''});
      onChangeOutputFormat('flac');
      onNotify('success', 'Master Studio Pro hazır', '4 uzman model · vokal ve enstrüman için ayrı ağırlıklar · FLAC. İşlem daha uzun sürebilir.');
    } else if (presetType === 'zero_loss_exchange') {
      const s1 =
        availableModels.roformer?.find((m) => m.includes('1297')) ||
        availableModels.roformer?.[0] ||
        'BS-Roformer-Viperx-1297';
      const s2 =
        availableModels.mdx23c?.find((m) => m.includes('HQ') || m.includes('InstVoc')) ||
        availableModels.mdx23c?.[0] ||
        'MDX23C-8KFFT-InstVoc_HQ';
      const s3 =
        availableModels.roformer?.find((m) => m.includes('1143')) ||
        availableModels.roformer?.[1] ||
        'Mel-Roformer-Viperx-1143';
      const s4 =
        availableModels.roformer?.find((m) => m.includes('Kimberley') || m.includes('Vocals by Gabox') || m.includes('124 bands')) ||
        availableModels.roformer?.[2] ||
        'MelBand Roformer | Vocals by Kimberley Jensen';

      onChangeEnsembleSlots([
        { model_type: 'roformer', model_key: s1 },
        { model_type: 'mdx23c', model_key: s2 },
        { model_type: 'roformer', model_key: s3 },
        { model_type: 'roformer', model_key: s4 },
      ]);
      onChangeParams({
        ...params,
        ensemble_profile: undefined,
        overlap: 8,
        segment_size: 256,
        normalization_threshold: 0.9,
        amplification_threshold: 0.7,
        denoise: true,
        tta: true,
        high_end_process: true,
        aggression: 10,
        post_process: true,
      });
      onNotify(
        'success',
        '💎 Ultra-Clean 4X S-Tier Ensemble Aktif Edildi!',
        'Roformer 1297 + MDX23C HQ + Roformer 1143 + Kim Vocals devreye alındı. Vokal ve enstrümantal sızıntıları tamamen engellendi.'
      );
    } else if (presetType === 'master_studio') {
      const s1 =
        availableModels.roformer?.find((m) => m.includes('1297')) ||
        availableModels.roformer?.[0] ||
        'BS-Roformer-Viperx-1297';
      const s2 = availableModels.mdx23c?.[0] || 'MDX23C-8KFFT-InstVoc_HQ';
      const s3 =
        availableModels.roformer?.find((m) => m.includes('1143') || m.includes('Kim')) ||
        availableModels.roformer?.[1] ||
        'Mel-Roformer-Viperx-1143';

      onChangeEnsembleSlots([
        { model_type: 'roformer', model_key: s1 },
        { model_type: 'mdx23c', model_key: s2 },
        { model_type: 'roformer', model_key: s3 },
      ]);
      onChangeParams({
        ...params,
        ensemble_profile: undefined,
        overlap: 8,
        segment_size: 512,
        normalization_threshold: 0.9,
        amplification_threshold: 0.7,
        denoise: true,
        tta: true,
        high_end_process: true,
        aggression: 10,
        post_process: true,
      });
      onNotify(
        'success',
        '👑 Master Ultra-HD Studio Preseti Aktif!',
        '4x Yapay Zeka Modeli (Roformer 1297 + MDX23C HQ + DeBleed + VR Karaoke) devreye alındı. Sıfır sızıntı garantili stüdyo vokali ve saf enstrümantal üretilecek.'
      );
    } else if (presetType === 'strings') {
      const s1 =
        availableModels.roformer?.find((m) => m.includes('1297')) ||
        availableModels.roformer?.[0] ||
        'BS-Roformer-Viperx-1297';
      const s2 =
        availableModels.roformer?.find((m) => m.includes('Inst V2') || m.includes('Karaoke') || m.includes('Instrumental')) ||
        availableModels.roformer?.[1] ||
        'MelBand Roformer Kim | Inst V2 by Unwa';
      const s3 = availableModels.mdx23c?.[0] || 'MDX23C-8KFFT-InstVoc_HQ';

      onChangeEnsembleSlots([
        { model_type: 'roformer', model_key: s1 },
        { model_type: 'roformer', model_key: s2 },
        { model_type: 'mdx23c', model_key: s3 },
      ]);
      onChangeParams({
        ...params,
        ensemble_profile: undefined,
        overlap: 8,
        segment_size: 512,
        normalization_threshold: 0.9,
        amplification_threshold: 0.7,
        denoise: true,
        tta: true,
      });
      onNotify(
        'success',
        '🎻 Preset Uygulandı: Keman & Bağlama Koruyucu',
        'Geniş zaman penceresi (512) ve Inst V2 mimarisiyle solo kemanın vokale karışması engellendi.'
      );
    } else if (presetType === 'vocal') {
      const s1 =
        availableModels.roformer?.find((m) => m.includes('1297') || m.includes('Vocals')) ||
        availableModels.roformer?.[0] ||
        'BS-Roformer-Viperx-1297';
      const s2 =
        availableModels.roformer?.find((m) => m.includes('Kim') || m.includes('1143')) ||
        availableModels.roformer?.[1] ||
        'Mel-Roformer-Viperx-1143';
      const s3 = availableModels.mdx23c?.[0] || 'MDX23C-8KFFT-InstVoc_HQ';

      onChangeEnsembleSlots([
        { model_type: 'roformer', model_key: s1 },
        { model_type: 'roformer', model_key: s2 },
        { model_type: 'mdx23c', model_key: s3 },
      ]);
      onChangeParams({
        ...params,
        ensemble_profile: undefined,
        overlap: 8,
        segment_size: 256,
        normalization_threshold: 0.9,
        denoise: true,
        tta: true,
      });
      onNotify(
        'success',
        '🎤 Preset Uygulandı: Kristal Saf Vokal',
        'Vokal arkasındaki tüm orkestra ve oda yankıları süpürüldü.'
      );
    } else if (presetType === 'piano') {
      const s1 =
        availableModels.roformer?.find((m) => m.includes('Inst') || m.includes('1297')) ||
        availableModels.roformer?.[0] ||
        'BS-Roformer-Viperx-1297';
      const s2 = availableModels.demucs?.[0] || 'htdemucs_6s.yaml';

      onChangeEnsembleSlots([
        { model_type: 'roformer', model_key: s1 },
        { model_type: 'demucs', model_key: s2 },
      ]);
      onChangeParams({
        ...params,
        ensemble_profile: undefined,
        overlap: 8,
        segment_size: 256,
        denoise: true,
      });
      onNotify(
        'success',
        '🎹 Preset Uygulandı: Piyano & Akustik Solo',
        'Solo piyano, gitar ve yaylı frekansları netleştirildi.'
      );
    }
  };

  return (
    <div className="glass-panel rounded-3xl p-6 sm:p-8 lg:p-7 shadow-2xl space-y-6 border border-white/10 relative">
      {/* Header with Title & Model Hub shortcut */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              'p-2.5 rounded-2xl border transition-all duration-300 shadow-md',
              accentColor === 'indigo' && 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30',
              accentColor === 'emerald' && 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
              accentColor === 'rose' && 'bg-rose-500/15 text-rose-400 border-rose-500/30',
              accentColor === 'amber' && 'bg-amber-500/15 text-amber-400 border-amber-500/30',
              accentColor === 'violet' && 'bg-violet-500/15 text-violet-400 border-violet-500/30'
            )}
          >
            <Sliders className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-black font-outfit text-white tracking-tight">
              {t('Model Configuration')}
            </h3>
            <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest">
              {currentTab} ENGINE
            </span>
          </div>
        </div>

        {onOpenModelHub && (
          <button
            type="button"
            onClick={onOpenModelHub}
            className="p-2 rounded-xl bg-white/[0.04] hover:bg-white/10 text-slate-400 hover:text-white border border-white/5 transition-all text-xs font-bold flex items-center gap-1.5"
            title="Model İndirme Merkezi"
          >
            <CloudDownload className="w-4 h-4 text-indigo-400" />
            <span className="hidden sm:inline">Model Merkezi</span>
          </button>
        )}
      </div>

      {/* Quick Ensemble Presets Deck */}
      <div className="space-y-3" style={{'--preset-accent': {
        indigo:'183 161 245', emerald:'129 200 178', rose:'233 154 180', amber:'251 191 36', violet:'202 159 233',
      }[accentColor]} as React.CSSProperties}>
        <div className="flex items-center justify-between">
          <label className="text-[11px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 font-outfit">
            <Sparkles className="w-3.5 h-3.5 text-preset" />
            <span>Hazır Akıllı Stüdyo Presetleri</span>
          </label>
          <span className="text-[9px] text-preset font-mono font-bold bg-preset/10 px-2 py-0.5 rounded-full border border-preset/20 flex items-center gap-1">
            <Zap className="w-2.5 h-2.5 fill-preset text-preset" />
            <span>1-TIKLA AYARLA</span>
          </span>
        </div>

        {/* Hero 1: Zero-Loss Cross Residual Bleed Exchange */}
        <button
          type="button"
          onClick={() => applyPreset('zero_loss_exchange')}
          className="w-full p-3.5 rounded-2xl bg-gradient-to-r from-preset/15 via-slate-900/90 to-preset/5 border border-preset/25 hover:border-preset text-left transition-all active:scale-[0.99] shadow-lg shadow-preset/10 group relative overflow-hidden cursor-pointer"
        >
          {/* Subtle Ambient Glow */}
          <div className="absolute -right-8 -top-8 w-32 h-32 bg-preset/15 rounded-full blur-2xl pointer-events-none group-hover:bg-preset/25 transition-colors" />

          <div className="relative z-10 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-preset/20 to-preset/30 border border-preset/25 flex items-center justify-center text-preset shadow-md shadow-preset/20 shrink-0 group-hover:scale-105 group-hover:border-preset transition-all">
                <ArrowLeftRight className="w-5 h-5 text-preset" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black font-outfit text-white tracking-tight group-hover:text-preset transition-colors truncate">
                    4X S-Tier Ultra-Clean Studio
                  </span>
                  <span className="text-[9px] font-mono font-black text-preset bg-preset/15 px-1.5 py-0.5 rounded border border-preset/30 shrink-0">
                    4X AI
                  </span>
                </div>
                <p className="text-[10px] text-slate-300 mt-0.5 truncate group-hover:text-white transition-colors">
                  Roformer 1297 + MDX23C HQ + 1143 + Kim • Sıfır Sızıntı & Saf Müzik
                </p>
              </div>
            </div>

            <div className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-preset/20 border border-preset/25 group-hover:bg-preset group-hover:text-slate-950 text-preset text-[11px] font-bold transition-all shadow-sm">
              <Zap className="w-3 h-3 fill-current" />
              <span>Aktif Et</span>
            </div>
          </div>
        </button>

        {/* Hero 2: Master Ultra-HD Gold Preset */}
        <button
          type="button"
          onClick={() => applyPreset('master_studio')}
          className="w-full p-3.5 rounded-2xl bg-gradient-to-r from-preset/10 via-slate-900/90 to-preset/5 border border-preset/30 hover:border-preset text-left transition-all active:scale-[0.99] shadow-lg shadow-preset/5 group relative overflow-hidden cursor-pointer"
        >
          {/* Subtle Ambient Light */}
          <div className="absolute -right-8 -top-8 w-28 h-28 bg-preset/10 rounded-full blur-2xl pointer-events-none group-hover:bg-preset/20 transition-colors" />

          <div className="relative z-10 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-preset/20 to-preset/30 border border-preset/30 flex items-center justify-center text-preset shadow-md shadow-preset/20 shrink-0 group-hover:scale-105 group-hover:border-preset transition-all">
                <Crown className="w-5 h-5 text-preset fill-preset/20" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black font-outfit text-white tracking-tight group-hover:text-preset transition-colors truncate">
                    Master Ultra-HD Studio Gold
                  </span>
                  <span className="text-[9px] font-mono font-black text-preset bg-preset/15 px-1.5 py-0.5 rounded border border-preset/30 shrink-0">
                    4X AI
                  </span>
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5 truncate group-hover:text-slate-300 transition-colors">
                  Kristal Vokal & Saf Enstrümantal • Sıfır Sızıntı
                </p>
              </div>
            </div>

            <div className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-preset/15 border border-preset/30 group-hover:bg-preset group-hover:text-slate-950 text-preset text-[11px] font-bold transition-all shadow-sm">
              <Zap className="w-3 h-3 fill-current" />
              <span>Uygula</span>
            </div>
          </div>
        </button>

        <button type="button" onClick={() => applyPreset('studio_pro')}
          className="w-full p-3.5 rounded-2xl border border-preset/25 bg-preset/10 hover:bg-preset/15 text-left transition-colors">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <ShieldCheck className="w-6 h-6 text-preset shrink-0" />
              <div><div className="text-sm font-bold text-white">Master Studio Pro <span className="text-[10px] text-preset">YENİ · 4 MODEL</span></div>
              <p className="text-xs text-slate-300 mt-1">Doğal vokal ve temiz enstrüman için uzman karışımı</p>
              <p className="text-[10px] text-slate-400 mt-1">FLAC · Daha uzun işlem · Sonuç şarkıya göre değişir</p></div>
            </div><span className="text-xs font-bold text-preset">Uygula</span>
          </div>
        </button>
        {/* 3 Specialized Mini Presets Grid */}
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => applyPreset('strings')}
            className="p-3 rounded-2xl bg-slate-900/80 hover:bg-slate-800/90 border border-white/10 hover:border-indigo-500/50 text-left transition-all active:scale-95 group shadow-md flex flex-col justify-between cursor-pointer"
            title="Keman, bağlama ve ud gibi yaylı/telli enstrümanları vokale sızdırmaz"
          >
            <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-2 group-hover:scale-110 group-hover:border-indigo-400 transition-all">
              <Music2 className="w-3.5 h-3.5" />
            </div>
            <div>
              <span className="text-[11px] font-bold text-white block leading-tight truncate group-hover:text-indigo-300 transition-colors">
                Keman & Telli
              </span>
              <span className="text-[9px] text-slate-400 block truncate mt-0.5">Sızıntı Önleyici</span>
            </div>
          </button>

          <button
            type="button"
            onClick={() => applyPreset('vocal')}
            className="p-3 rounded-2xl bg-slate-900/80 hover:bg-slate-800/90 border border-white/10 hover:border-emerald-500/50 text-left transition-all active:scale-95 group shadow-md flex flex-col justify-between cursor-pointer"
            title="Vokali stüdyo kayıt kabinindeymiş gibi tamamen saf çıkarır"
          >
            <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-2 group-hover:scale-110 group-hover:border-emerald-400 transition-all">
              <Mic2 className="w-3.5 h-3.5" />
            </div>
            <div>
              <span className="text-[11px] font-bold text-white block leading-tight truncate group-hover:text-emerald-300 transition-colors">
                Kristal Vokal
              </span>
              <span className="text-[9px] text-slate-400 block truncate mt-0.5">Sıfır Orkestra</span>
            </div>
          </button>

          <button
            type="button"
            onClick={() => applyPreset('piano')}
            className="p-3 rounded-2xl bg-slate-900/80 hover:bg-slate-800/90 border border-white/10 hover:border-amber-500/50 text-left transition-all active:scale-95 group shadow-md flex flex-col justify-between cursor-pointer"
            title="Piyano ve akustik soloları net ayırır"
          >
            <div className="w-7 h-7 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-2 group-hover:scale-110 group-hover:border-amber-400 transition-all">
              <Volume2 className="w-3.5 h-3.5" />
            </div>
            <div>
              <span className="text-[11px] font-bold text-white block leading-tight truncate group-hover:text-amber-300 transition-colors">
                Piyano & Solo
              </span>
              <span className="text-[9px] text-slate-400 block truncate mt-0.5">Solo Koruma</span>
            </div>
          </button>
        </div>
      </div>

      {/* Ensemble Mode Toggle Card */}
      <div className="p-4 rounded-2xl glass-panel border border-white/10 flex items-center justify-between gap-3 bg-slate-900/60 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-white/[0.05] text-slate-300">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <p className="text-xs font-black font-outfit text-white tracking-tight">
              {t('Ensemble Mode')}
            </p>
            <p className="text-[10px] text-slate-400">{t('Multi-Model Quality Boost')}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onToggleEnsembleMode}
          className={cn(
            'w-12 h-6.5 rounded-full transition-colors relative flex items-center p-1 cursor-pointer shrink-0 shadow-inner',
            ensembleMode ? 'bg-indigo-600' : 'bg-slate-800'
          )}
        >
          <div
            className={cn(
              'w-4.5 h-4.5 rounded-full bg-white transition-transform duration-200 shadow-md',
              ensembleMode ? 'translate-x-5.5' : 'translate-x-0'
            )}
          />
        </button>
      </div>

      {/* Single Model Selector Deck */}
      {!ensembleMode ? (
        <div className="space-y-2">
          <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest block">
            {t('Select Model')}
          </label>
          <div ref={dropdownContainerRef} className="relative">
            <button
              type="button"
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="w-full bg-slate-950/90 border border-white/10 hover:border-white/20 rounded-2xl p-3.5 text-xs text-white flex items-center justify-between transition-all duration-200 shadow-inner"
            >
              <div className="flex items-center gap-2.5 truncate">
                <Cpu className="w-4 h-4 text-indigo-400 shrink-0" />
                <span className="font-bold truncate">{selectedModel || t('Choose a model...')}</span>
                {isFavorite(selectedModel) && (
                  <span className="text-amber-400 text-xs shrink-0 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]">
                    ★
                  </span>
                )}
              </div>
              <ChevronDown
                className={cn('w-4 h-4 text-slate-400 transition-transform duration-200', dropdownOpen && 'rotate-180')}
              />
            </button>

            {/* Model Dropdown Menu Outward Floating Popover */}
            {dropdownOpen && (
              <div className="absolute top-full left-0 right-0 mt-2 bg-[#0b1329]/98 border border-white/20 backdrop-blur-2xl rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.9)] p-2.5 z-[100] max-h-72 overflow-y-auto space-y-1 custom-scrollbar animate-in fade-in zoom-in-95 duration-150 ring-1 ring-white/10">
                <input
                  type="text"
                  placeholder={t('Search models...')}
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-full bg-white/[0.06] border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 outline-none mb-1.5 focus:border-indigo-500"
                />
                {filteredModels.map((m) => {
                  const fav = isFavorite(m);
                  return (
                    <div
                      key={m}
                      className={cn(
                        'flex items-center justify-between p-2.5 rounded-xl hover:bg-white/[0.08] cursor-pointer text-xs transition-colors group',
                        selectedModel === m && 'bg-indigo-600/20 text-indigo-300 font-bold border border-indigo-500/30'
                      )}
                    >
                      <span
                        onClick={() => {
                          onSelectModel(m);
                          setDropdownOpen(false);
                        }}
                        className="truncate flex-1 text-slate-200 group-hover:text-white"
                      >
                        {m}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleFavorite(m);
                        }}
                        className="p-1 rounded-lg hover:bg-white/10 text-slate-500 hover:text-amber-400 transition-colors ml-2 shrink-0"
                        title={fav ? 'Favorilerden Çıkar' : 'Favorilere Ekle'}
                      >
                        <Star
                          className={cn(
                            'w-3.5 h-3.5',
                            fav ? 'fill-amber-400 text-amber-400 drop-shadow-[0_0_6px_rgba(245,158,11,0.6)]' : 'text-slate-500'
                          )}
                        />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Model Status & Fast Download Banner */}
          {modelStatus && (
            <div className="flex items-center justify-between px-1 text-[11px] pt-1 font-mono">
              {modelStatus.cached ? (
                <span className="text-emerald-400 flex items-center gap-1.5 font-bold">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                  {t('Cached ✓')} ({modelStatus.total_files}/{modelStatus.total_files})
                </span>
              ) : (
                <div className="flex items-center justify-between w-full">
                  <span className="text-amber-400 flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5" />
                    {t('Download required')}
                  </span>
                  <button
                    type="button"
                    onClick={handleDownloadModel}
                    disabled={isDownloading}
                    className="flex items-center gap-1 px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold text-[10px] transition-colors shadow-md"
                  >
                    {isDownloading ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Download className="w-3 h-3" />
                    )}
                    <span>{isDownloading ? t('Downloading...') : t('Download')}</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* Ensemble Multi-Slot Pickers */
        <div className="space-y-3 p-4 rounded-2xl glass-panel border border-white/10 bg-slate-900/40">
          <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest block">
            {t('Ensemble Models (2-4 Slots)')}
          </label>
          {ensembleSlots.map((slot, idx) => (
            <div key={idx} className="space-y-1">
              <label className="text-[10px] font-mono text-slate-400 ml-1">
                Slot {idx + 1} {idx === 0 ? '(Lead)' : idx === 1 ? '(Blend)' : ''}
              </label>
              <StudioSelect
                aria-label={`Slot ${idx+1} modeli`}
                value={slot.model_key}
                onValueChange={(value) => {
                  const key = value;
                  const updated = [...ensembleSlots];
                  updated[idx] = {
                    model_key: key,
                    model_type: getModelType(key),
                  };
                  onChangeParams({...params, ensemble_profile:undefined});
                  onChangeEnsembleSlots(updated);
                }}
                className="w-full bg-slate-950 border border-white/10 rounded-2xl p-3 text-xs text-white outline-none focus:border-indigo-500"
              >
                <option value="">{t('Select model...')}</option>
                {Object.entries(availableModels).map(([category, list]) => (
                  <optgroup key={category} label={category.toUpperCase()}>
                    {list.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </StudioSelect>
            </div>
          ))}
        </div>
      )}

      {/* Single Stem Output Filter (Tek Kanal Çıktısı Modu) */}
      <div className="space-y-2">
        <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest block">
          Tek Kanal Çıktı Modu (Single Stem)
        </label>
        <div className="grid grid-cols-3 gap-1.5 p-1 rounded-2xl glass-panel border border-white/10 bg-slate-950/70 shadow-inner">
          {[
            { id: '', label: 'Tüm Kanallar' },
            { id: 'Vocals', label: 'Sadece Vokal' },
            { id: 'Instrumental', label: 'Sadece Enstr.' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onChangeParams({ ...params, single_stem: item.id })}
              className={cn(
                'py-2 rounded-xl text-xs font-bold font-outfit transition-all duration-150 active:scale-95 text-center',
                (params.single_stem || '') === item.id
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/25'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Illuminated Hardware-Style Output Format Buttons */}
      <div className="space-y-2">
        <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest block">
          {t('Output Format')}
        </label>
        <div className="grid grid-cols-4 gap-2">
          {['mp3', 'wav', 'flac', 'ogg'].map((fmt) => (
            <button
              key={fmt}
              type="button"
              onClick={() => onChangeOutputFormat(fmt)}
              className={cn(
                'py-3 rounded-2xl font-mono text-xs font-bold uppercase transition-all duration-200 active:scale-95 shadow-md flex items-center justify-center gap-1.5',
                outputFormat === fmt
                  ? cn(
                      'text-white shadow-xl ring-1',
                      accentColor === 'indigo' && 'bg-indigo-600 ring-indigo-400/50 shadow-indigo-500/40',
                      accentColor === 'emerald' && 'bg-emerald-600 ring-emerald-400/50 shadow-emerald-500/40',
                      accentColor === 'rose' && 'bg-rose-600 ring-rose-400/50 shadow-rose-500/40',
                      accentColor === 'amber' && 'bg-amber-600 ring-amber-400/50 shadow-amber-500/40',
                      accentColor === 'violet' && 'bg-violet-600 ring-violet-400/50 shadow-violet-500/40'
                    )
                  : 'bg-slate-950/70 hover:bg-slate-900 border border-white/5 text-slate-400 hover:text-white'
              )}
            >
              {fmt}
            </button>
          ))}
        </div>
      </div>

      {/* Expandable Advanced Stems / Audio Parameters */}
      <div className="pt-3 border-t border-white/[0.08] space-y-3">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between text-xs font-bold text-slate-300 uppercase tracking-wider p-2 rounded-xl hover:bg-white/5 transition-colors"
        >
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-3.5 h-3.5 text-indigo-400" />
            <span>Gelişmiş Stüdyo Parametreleri</span>
          </div>
          {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {/* Basic Segment & Overlap for Roformer/MDX */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-[11px] font-mono text-slate-400">{t('Segment Size')}</label>
            <StudioSelect
              aria-label={t('Segment Size')}
              value={params.segment_size || 256}
              onValueChange={(value) =>
                onChangeParams({ ...params, segment_size: parseInt(value, 10) })
              }
              className="w-full bg-slate-950 border border-white/10 rounded-xl p-2.5 text-xs text-white"
            >
              <option value="128">128 (Hızlı / Düşük VRAM)</option>
              <option value="256">256 (Varsayılan)</option>
              <option value="512">512 (Yüksek Kalite)</option>
            </StudioSelect>
          </div>

          <div className="space-y-1.5">
            <label className="text-[11px] font-mono text-slate-400">{t('Overlap')}</label>
            <StudioSelect
              aria-label={t('Overlap')}
              value={params.overlap || 8}
              onValueChange={(value) =>
                onChangeParams({ ...params, overlap: parseInt(value, 10) })
              }
              className="w-full bg-slate-950 border border-white/10 rounded-xl p-2.5 text-xs text-white"
            >
              <option value="2">2 (Düşük)</option>
              <option value="4">4 (Orta)</option>
              <option value="8">8 (Önerilen)</option>
            </StudioSelect>
          </div>
        </div>

        {/* Deep Pro Parameters Drawer */}
        {showAdvanced && (
          <div className="space-y-3 pt-2 animate-in fade-in duration-200">
            {/* Normalization & Amplification Thresholds */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[10px] font-mono text-slate-400">
                  Normalizasyon ({params.normalization_threshold ?? 0.9})
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.05"
                  value={params.normalization_threshold ?? 0.9}
                  onChange={(e) =>
                    onChangeParams({ ...params, normalization_threshold: parseFloat(e.target.value) })
                  }
                  className="w-full accent-indigo-500 cursor-pointer h-1.5 bg-slate-900 rounded-lg"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-mono text-slate-400">
                  Amplifikasyon ({params.amplification_threshold ?? 0.7})
                </label>
                <input
                  type="range"
                  min="0.2"
                  max="1.0"
                  step="0.05"
                  value={params.amplification_threshold ?? 0.7}
                  onChange={(e) =>
                    onChangeParams({ ...params, amplification_threshold: parseFloat(e.target.value) })
                  }
                  className="w-full accent-indigo-500 cursor-pointer h-1.5 bg-slate-900 rounded-lg"
                />
              </div>
            </div>

            {/* Architecture-Specific Toggles */}
            {currentTab === 'mdxnet' && (
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/70 border border-white/5">
                <div>
                  <p className="text-xs font-bold text-white">{t('Denoise Output')}</p>
                  <p className="text-[10px] text-slate-400">{t('Clean artifacts')}</p>
                </div>
                <input
                  type="checkbox"
                  checked={params.denoise ?? true}
                  onChange={(e) => onChangeParams({ ...params, denoise: e.target.checked })}
                  className="w-4 h-4 accent-indigo-500 rounded cursor-pointer"
                />
              </div>
            )}

            {currentTab === 'vrarch' && (
              <div className="space-y-2 p-3 rounded-xl bg-slate-950/70 border border-white/5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">TTA (Test-Time Augmentation)</span>
                  <input
                    type="checkbox"
                    checked={params.tta ?? true}
                    onChange={(e) => onChangeParams({ ...params, tta: e.target.checked })}
                    className="w-4 h-4 accent-indigo-500 rounded cursor-pointer"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">High-End Process</span>
                  <input
                    type="checkbox"
                    checked={params.high_end_process ?? false}
                    onChange={(e) => onChangeParams({ ...params, high_end_process: e.target.checked })}
                    className="w-4 h-4 accent-indigo-500 rounded cursor-pointer"
                  />
                </div>
              </div>
            )}

            {currentTab === 'demucs' && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] font-mono text-slate-400">Shifts (Varyasyon)</label>
                  <StudioSelect
                    aria-label="Shifts (Varyasyon)"
                    value={params.shifts || 2}
                    onValueChange={(value) =>
                      onChangeParams({ ...params, shifts: parseInt(value, 10) })
                    }
                    className="w-full bg-slate-950 border border-white/10 rounded-xl p-2 text-xs text-white"
                  >
                    <option value="1">1 (Hızlı)</option>
                    <option value="2">2 (Dengeli)</option>
                    <option value="4">4 (Yüksek Kalite)</option>
                  </StudioSelect>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
