'use client';

import React, { useState, useEffect } from 'react';
import {
  X,
  Download,
  CheckCircle2,
  Loader2,
  CloudDownload,
  Search,
  Cpu,
  Layers,
  Sparkles,
  Crown,
  Zap,
} from 'lucide-react';
import { Language, AccentColor, AvailableModels, ModelStatus } from '@/lib/types';
import { cn } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';

interface ModelDownloaderModalProps {
  isOpen: boolean;
  onClose: () => void;
  lang: Language;
  accentColor: AccentColor;
  availableModels: AvailableModels;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const ModelDownloaderModal: React.FC<ModelDownloaderModalProps> = ({
  isOpen,
  onClose,
  lang,
  accentColor,
  availableModels,
  onNotify,
}) => {
  const t = (key: string) => getTranslation(lang, key);

  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [modelStatuses, setModelStatuses] = useState<Record<string, ModelStatus>>({});
  const [downloadingKeys, setDownloadingKeys] = useState<Record<string, number>>({});
  const [whisperModelsList, setWhisperModelsList] = useState<
    Array<{
      key: string;
      model_name: string;
      installed: boolean;
      size_mb: number;
      desc: string;
      recommended: boolean;
    }>
  >([
    {
      key: 'large-v3',
      model_name: 'Whisper Large-V3 (Full HQ - 32 Katman)',
      installed: false,
      size_mb: 0,
      desc: 'Maksimum doğruluk, 1.55B parametre ve 32 katmanlı derin yapay zeka',
      recommended: true,
    },
    {
      key: 'large-v3-turbo',
      model_name: 'Whisper Large-V3-Turbo (Hızlı)',
      installed: false,
      size_mb: 0,
      desc: 'Ultra hızlı, 4 katmanlı şarkı sözü çıkarma modeli',
      recommended: false,
    },
  ]);
  const [whisperDownloadingKeys, setWhisperDownloadingKeys] = useState<Record<string, boolean>>({});

  // Flatten all models with their categories
  const allModelList: { key: string; category: string }[] = [];
  Object.entries(availableModels).forEach(([cat, models]) => {
    models.forEach((m) => {
      allModelList.push({ key: m, category: cat });
    });
  });

  // Check cache status of models when modal opens
  useEffect(() => {
    if (!isOpen) return;

    api
      .getWhisperStatus()
      .then((st) => {
        if (st.models && st.models.length > 0) {
          setWhisperModelsList(st.models);
        }
      })
      .catch(() => {});

    allModelList.forEach((m) => {
      api
        .getModelStatus(m.key)
        .then((st) => {
          setModelStatuses((prev) => ({ ...prev, [m.key]: st }));
        })
        .catch(() => {});
    });
  }, [isOpen, availableModels]);

  const handleDownloadWhisper = async (modelKey: string = 'large-v3') => {
    const isFull = modelKey === 'large-v3';
    const label = isFull ? 'Whisper Large-V3 (Full HQ ~3.1 GB)' : 'Whisper Large-V3-Turbo (~1.5 GB)';
    setWhisperDownloadingKeys((prev) => ({ ...prev, [modelKey]: true }));
    onNotify('info', 'Whisper İndirmesi Başlatıldı', `${label} indiriliyor...`);
    try {
      const res = await api.downloadWhisperModel(modelKey);
      const taskId = res.task_id;
      const poll = setInterval(async () => {
        try {
          const st = await api.getTaskStatus(taskId);
          if (st.status === 'completed') {
            clearInterval(poll);
            setWhisperDownloadingKeys((prev) => ({ ...prev, [modelKey]: false }));
            api
              .getWhisperStatus()
              .then((ws) => {
                if (ws.models) setWhisperModelsList(ws.models);
              })
              .catch(() => {});
            onNotify('success', 'Whisper Kuruldu!', `${label} başarıyla kuruldu.`);
          } else if (st.status === 'failed') {
            clearInterval(poll);
            setWhisperDownloadingKeys((prev) => ({ ...prev, [modelKey]: false }));
            onNotify('error', 'İndirme Başarısız', st.error || 'Whisper modeli indirilemedi');
          }
        } catch {}
      }, 1500);
    } catch (err: any) {
      setWhisperDownloadingKeys((prev) => ({ ...prev, [modelKey]: false }));
      onNotify('error', 'İndirme Hatası', err.message);
    }
  };

  const handleStartDownload = async (modelKey: string) => {
    if (downloadingKeys[modelKey] !== undefined) return;

    setDownloadingKeys((prev) => ({ ...prev, [modelKey]: 5 }));
    onNotify('info', 'Model Download Started', `${modelKey} is downloading from cloud.`);

    try {
      const res = await api.downloadModel(modelKey);
      const taskId = res.task_id;

      const poll = setInterval(async () => {
        try {
          const st = await api.getTaskStatus(taskId);
          const raw = st.progress || 0.1;
          const pct = Math.round(raw <= 1.0 ? raw * 100 : raw);
          setDownloadingKeys((prev) => ({ ...prev, [modelKey]: pct }));

          if (st.status === 'completed') {
            clearInterval(poll);
            setDownloadingKeys((prev) => {
              const updated = { ...prev };
              delete updated[modelKey];
              return updated;
            });
            setModelStatuses((prev) => ({
              ...prev,
              [modelKey]: { cached: true, total_files: 1, existing: [modelKey] },
            }));
            onNotify('success', 'Model Downloaded!', `${modelKey} is ready for local AI inference.`);
          } else if (st.status === 'failed') {
            clearInterval(poll);
            setDownloadingKeys((prev) => {
              const updated = { ...prev };
              delete updated[modelKey];
              return updated;
            });
            onNotify('error', 'Download Failed', st.error || st.message);
          }
        } catch (e) {
          clearInterval(poll);
          setDownloadingKeys((prev) => {
            const updated = { ...prev };
            delete updated[modelKey];
            return updated;
          });
        }
      }, 1500);
    } catch (e: any) {
      setDownloadingKeys((prev) => {
        const updated = { ...prev };
        delete updated[modelKey];
        return updated;
      });
      onNotify('error', 'Download Error', e.message || 'Could not start download');
    }
  };

  if (!isOpen) return null;

  const filteredModels = allModelList.filter((m) => {
    const matchesCat = activeCategory === 'all' || m.category === activeCategory;
    const matchesSearch =
      !searchFilter.trim() || m.key.toLowerCase().includes(searchFilter.toLowerCase().trim());
    return matchesCat && matchesSearch;
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xl animate-in fade-in duration-200">
      <div className="glass-panel w-full max-w-6xl max-h-[85vh] rounded-3xl p-6 sm:p-8 flex flex-col gap-6 shadow-2xl border border-white/15 relative overflow-hidden bg-slate-950/90">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4 shrink-0">
          <div className="flex items-center gap-3.5">
            <div className="p-3 rounded-2xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 shadow-[0_0_15px_rgba(99,102,241,0.2)]">
              <CloudDownload className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-xl font-black font-outfit text-white tracking-tight">
                Model İndirme & Yönetim Merkezi
              </h3>
              <p className="text-xs text-slate-400">
                UVR5 yapay zeka modellerini tek tıkla cihazınıza indirin ve önbelleği yönetin.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2.5 rounded-2xl hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filters & Search */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 shrink-0">
          {/* Category Tabs */}
          <div className="flex items-center gap-1 p-1 rounded-2xl glass-panel border border-white/10 w-full sm:w-auto overflow-x-auto custom-scrollbar">
            {[
              { id: 'all', label: 'Tümü' },
              { id: 'roformer', label: 'Roformer' },
              { id: 'mdx23c', label: 'MDX23C' },
              { id: 'mdxnet', label: 'MDX-NET' },
              { id: 'vrarch', label: 'VR Arch' },
              { id: 'demucs', label: 'Demucs' },
            ].map((cat) => (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className={cn(
                  'px-3.5 py-1.5 rounded-xl text-xs font-bold font-outfit transition-all shrink-0',
                  activeCategory === cat.id
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/20'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                )}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Search Input */}
          <div className="glass-panel px-3 py-2 rounded-2xl border border-white/10 flex items-center gap-2 w-full sm:w-64">
            <Search className="w-4 h-4 text-slate-400 shrink-0" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Model ara..."
              className="bg-transparent text-xs text-white placeholder-slate-500 outline-none w-full"
            />
          </div>
        </div>

        {/* Models Grid (Scrollable) */}
        <div className="overflow-y-auto custom-scrollbar flex-1 pr-1 space-y-2.5">
          {/* Whisper Speech-to-Text & Karaoke Models Section */}
          {(activeCategory === 'all' || activeCategory === 'roformer') &&
            whisperModelsList
              .filter(
                (wm) =>
                  !searchFilter ||
                  wm.model_name.toLowerCase().includes(searchFilter.toLowerCase()) ||
                  wm.key.toLowerCase().includes(searchFilter.toLowerCase()) ||
                  'whisper söz karaoke transkripsiyon full hq turbo'.includes(searchFilter.toLowerCase())
              )
              .map((wm) => {
                const isDownloading = !!whisperDownloadingKeys[wm.key];
                const isFull = wm.key === 'large-v3';

                return (
                  <div
                    key={wm.key}
                    className={cn(
                      'p-4 rounded-2xl border flex items-center justify-between gap-4 shadow-lg transition-all',
                      isFull
                        ? 'border-amber-500/40 bg-gradient-to-r from-amber-950/40 via-slate-900/70 to-indigo-950/40 shadow-amber-500/10'
                        : 'border-indigo-500/30 bg-gradient-to-r from-indigo-950/30 via-slate-900/60 to-slate-950/50 shadow-indigo-500/5'
                    )}
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <div
                        className={cn(
                          'p-2.5 rounded-xl border shrink-0',
                          isFull
                            ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                            : 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30'
                        )}
                      >
                        {isFull ? <Crown className="w-4 h-4" /> : <Zap className="w-4 h-4" />}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-black text-white truncate font-outfit">
                            {wm.model_name}
                          </span>
                          {isFull ? (
                            <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0">
                              👑 32 KATMAN • EN YÜKSEK DOĞRULUK (~3.1 GB)
                            </span>
                          ) : (
                            <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shrink-0">
                              ⚡ HIZLI SENKRON (~1.5 GB)
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          {wm.installed ? (
                            <span className="text-emerald-400 font-medium flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" /> Cihazınızda kurulu (
                              {wm.size_mb > 0 ? `${wm.size_mb} MB` : isFull ? '3.1 GB' : '1.5 GB'})
                            </span>
                          ) : (
                            <span className={isFull ? 'text-amber-300/80' : 'text-slate-400'}>
                              {wm.desc}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="shrink-0">
                      {isDownloading ? (
                        <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-bold font-mono animate-pulse">
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>İndiriliyor...</span>
                        </div>
                      ) : wm.installed ? (
                        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Kurulu</span>
                        </div>
                      ) : (
                        <button
                          onClick={() => handleDownloadWhisper(wm.key)}
                          className={cn(
                            'flex items-center gap-1.5 px-4 py-2 rounded-xl font-black text-xs transition-all shadow-md active:scale-95 cursor-pointer',
                            isFull
                              ? 'bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 shadow-amber-500/20'
                              : 'bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white shadow-indigo-500/20'
                          )}
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Modeli İndir</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}

          {filteredModels.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-xs">Model bulunamadı.</div>
          ) : (
            filteredModels.map((m) => {
              const status = modelStatuses[m.key];
              const isCached = status?.cached === true;
              const downloadPct = downloadingKeys[m.key];
              const isDownloading = downloadPct !== undefined;

              return (
                <div
                  key={m.key}
                  className="p-4 rounded-2xl glass-panel border border-white/10 flex items-center justify-between gap-4 hover:border-white/20 transition-all bg-slate-900/60"
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className="p-2.5 rounded-xl bg-slate-800 text-slate-300 border border-white/5 shrink-0">
                      <Cpu className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white truncate">{m.key}</span>
                        <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-md bg-white/[0.05] text-indigo-300 border border-white/5 shrink-0">
                          {m.category}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5">
                        {isCached ? (
                          <span className="text-emerald-400 font-medium flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> Cihazınızda mevcut (Önbellekte)
                          </span>
                        ) : (
                          <span className="text-slate-500">Buluttan indirilmeye hazır</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="shrink-0">
                    {isDownloading ? (
                      <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-bold font-mono">
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>%{downloadPct}</span>
                      </div>
                    ) : isCached ? (
                      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>İndirildi</span>
                      </div>
                    ) : (
                      <button
                        onClick={() => handleStartDownload(m.key)}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-md shadow-indigo-500/20 active:scale-95"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>İndir</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-white/10 text-xs text-slate-400 shrink-0">
          <span>Toplam {filteredModels.length} model listeleniyor</span>
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-white/[0.05] hover:bg-white/10 text-white font-bold transition-colors"
          >
            Kapat
          </button>
        </div>
      </div>
    </div>
  );
};
