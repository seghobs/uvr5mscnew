'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  TabId,
  Language,
  AccentColor,
  AvailableModels,
  SeparationParams,
  EnsembleSlot,
  LibraryItem,
} from '@/lib/types';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';
import { Header } from '@/components/Header';
import { NavigationTabs } from '@/components/NavigationTabs';
import { UploadZone, UploadedItem } from '@/components/UploadZone';
import { ModelConfiguration } from '@/components/ModelConfiguration';
import { StemAudioPlayer } from '@/components/StemAudioPlayer';
import { StudioRemix } from '@/components/StudioRemix';
import { LibraryView } from '@/components/LibraryView';
import { LeaderboardView } from '@/components/LeaderboardView';
import { BatchProcessingView } from '@/components/BatchProcessingView';
import { ModelDownloaderModal } from '@/components/ModelDownloaderModal';
import { SettingsModal } from '@/components/SettingsModal';
import { ToastContainer, ToastMessage } from '@/components/Toast';
import { Loader2, Sparkles, CheckCircle2, Music, Info } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function StudioPage() {
  // Localization & Theme
  const [lang, setLang] = useState<Language>('tr');
  const [accentColor, setAccentColor] = useState<AccentColor>('indigo');

  useEffect(() => {
    try {
      const savedLang = localStorage.getItem('uvr_lang') as Language;
      if (savedLang && (savedLang === 'tr' || savedLang === 'en')) setLang(savedLang);
      const savedAccent = localStorage.getItem('uvr_accent') as AccentColor;
      if (savedAccent) setAccentColor(savedAccent);
    } catch {}
  }, []);

  const handleToggleLang = () => {
    const nextLang = lang === 'tr' ? 'en' : 'tr';
    setLang(nextLang);
    try {
      localStorage.setItem('uvr_lang', nextLang);
    } catch {}
  };

  const handleChangeAccent = (color: AccentColor) => {
    setAccentColor(color);
    try {
      localStorage.setItem('uvr_accent', color);
    } catch {}
  };

  const t = (key: string) => getTranslation(lang, key);

  // Tab State
  const [currentTab, setCurrentTab] = useState<TabId>('roformer');

  // Backend Models State
  const [availableModels, setAvailableModels] = useState<AvailableModels>({});
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [outputFormat, setOutputFormat] = useState<string>('flac');
  const [device, setDevice] = useState<string>('CUDA (Auto)');
  const [showSettings, setShowSettings] = useState(false);
  const [isModelHubOpen, setIsModelHubOpen] = useState(false);

  // Separation Parameters
  const [params, setParams] = useState<SeparationParams>({
    segment_size: 256,
    override_segment_size: false,
    overlap: 8,
    batch_size: 1,
    normalization_threshold: 0.9,
    amplification_threshold: 0.7,
    single_stem: '',
    hop_length: 1024,
    denoise: true,
    window_size: 512,
    aggression: 5,
    tta: true,
    post_process: false,
    post_process_threshold: 0.2,
    high_end_process: false,
    shifts: 2,
    segments_enabled: true,
  });

  // Ensemble Mode State
  const [ensembleMode, setEnsembleMode] = useState(false);
  const [ensembleSlots, setEnsembleSlots] = useState<EnsembleSlot[]>([
    { model_type: 'roformer', model_key: '' },
    { model_type: 'mdx23c', model_key: '' },
  ]);

  // Queue & Uploaded Audio
  const [queue, setQueue] = useState<UploadedItem[]>([]);

  // Task & Processing State
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [processingMessage, setProcessingMessage] = useState('');
  const [separatedStems, setSeparatedStems] = useState<string[]>([]);

  // Notifications
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const addToast = (
    type: 'success' | 'error' | 'warning' | 'info',
    title: string,
    message?: string,
    duration?: number
  ) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => {
      // Limit to latest 4 toasts to keep viewport neat and clean
      const updated = [...prev, { id, type, title, message, duration }];
      return updated.slice(-4);
    });
  };
  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Fetch Available Models from Backend
  useEffect(() => {
    api
      .getModels()
      .then((data) => {
        setAvailableModels(data);
        if (data.roformer && data.roformer.length > 0) {
          setSelectedModel(data.roformer[0]);
        }
        if (data.roformer && data.mdx23c) {
          setEnsembleSlots([
            { model_type: 'roformer', model_key: data.roformer[0] || '' },
            { model_type: 'mdx23c', model_key: data.mdx23c[0] || '' },
          ]);
        }
      })
      .catch((err) => {
        console.error('Failed to load models:', err);
      });
  }, []);

  // Update default model on Tab Change
  const handleSelectTab = (tab: TabId) => {
    setCurrentTab(tab);
    if (tab === 'library' || tab === 'leaderboard' || tab === 'batch') return;
    const models = availableModels[tab] || [];
    if (models.length > 0 && !models.includes(selectedModel)) {
      setSelectedModel(models[0]);
    }
  };

  // Start AI Separation Process
  const handleStartSeparation = async () => {
    if (queue.length === 0) {
      addToast('warning', 'Queue Empty', 'Please upload or search for an audio track first.');
      return;
    }

    const currentItem = queue[0];
    if (!currentItem || !currentItem.path) {
      addToast('error', 'Invalid File', 'Could not locate uploaded audio path.');
      return;
    }

    setIsProcessing(true);
    setProgress(10);
    setProcessingMessage('Initializing AI neural network models...');
    setSeparatedStems([]);

    try {
      let taskId = '';

      if (ensembleMode) {
        const validSlots = ensembleSlots.filter((s) => s.model_key);
        if (validSlots.length < 2) {
          addToast('warning', 'Ensemble Configuration', 'Please select at least 2 models for ensemble.');
          setIsProcessing(false);
          return;
        }
        const res = await api.startEnsemble({
          models: validSlots,
          audio_path: currentItem.path,
          out_format: outputFormat,
          params,
        });
        taskId = res.task_id;
      } else {
        if (!selectedModel) {
          addToast('warning', 'Model Missing', 'Please select an AI model first.');
          setIsProcessing(false);
          return;
        }
        const res = await api.startSeparation({
          model_type: currentTab,
          model_key: selectedModel,
          audio_path: currentItem.path,
          out_format: outputFormat,
          params,
        });
        taskId = res.task_id;
      }

      // Poll task status
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await api.getTaskStatus(taskId);
          const rawProg = statusRes.progress ?? 0.1;
          const pct = Math.round(rawProg <= 1.0 ? rawProg * 100 : rawProg);
          setProgress(Math.max(5, Math.min(100, pct)));
          setProcessingMessage(statusRes.message || 'Processing audio with neural network...');

          if (statusRes.status === 'completed') {
            clearInterval(pollInterval);
            setIsProcessing(false);
            setProgress(100);

            const stems =
              Array.isArray(statusRes.stems) && statusRes.stems.length > 0
                ? statusRes.stems
                : Array.isArray(statusRes.results) && statusRes.results.length > 0
                ? statusRes.results
                : [];
            setSeparatedStems(stems);
            addToast('success', 'Separation Complete!', `${stems.length} stems ready for preview.`);

            // Scroll down to stems smoothly
            setTimeout(() => {
              document.getElementById('separated-stems-section')?.scrollIntoView({
                behavior: 'smooth',
                block: 'start',
              });
            }, 100);

            // Add to library history
            try {
              const prevLib: LibraryItem[] = JSON.parse(
                localStorage.getItem('uvr_library') || '[]'
              );
              const newEntry: LibraryItem = {
                id: Date.now(),
                filename: currentItem.name,
                stems,
                timestamp: new Date().toLocaleTimeString(),
              };
              const updatedLib = [newEntry, ...prevLib];
              localStorage.setItem('uvr_library', JSON.stringify(updatedLib));
            } catch (err) {
              console.error(err);
            }
          } else if (statusRes.status === 'failed') {
            clearInterval(pollInterval);
            setIsProcessing(false);
            addToast('error', 'Separation Failed', statusRes.error || statusRes.message);
          }
        } catch (err: any) {
          clearInterval(pollInterval);
          setIsProcessing(false);
          addToast('error', 'Network Error', err.message);
        }
      }, 1200);
    } catch (e: any) {
      setIsProcessing(false);
      addToast('error', 'Error starting separation', e.message);
    }
  };

  // Load Project Session from Library (PSD Style)
  const handleLoadProject = (project: LibraryItem) => {
    // 1. Set Queue with loaded file
    const loadedItem: UploadedItem = {
      id: `${project.id || Date.now()}`,
      name: project.filename,
      path: project.filename,
      size: 0,
    };
    setQueue([loadedItem]);

    // 2. Restore separated stems
    setSeparatedStems(project.stems || []);

    // 3. Switch back to studio workspace tab
    setCurrentTab('roformer');

    // 4. Toast notification
    addToast(
      'success',
      '📂 Proje Oturumu Yüklendi!',
      `"${project.filename}" çalışmasına başarıyla geri dönüldü (${(project.stems || []).length} stem yüklendi).`
    );

    // 5. Scroll down to separated stems
    setTimeout(() => {
      document.getElementById('separated-stems-section')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    }, 150);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500/30 font-sans">
      <Header
        lang={lang}
        accentColor={accentColor}
        onToggleLang={handleToggleLang}
        onChangeAccent={handleChangeAccent}
        onOpenSettings={() => setShowSettings(true)}
        onOpenModelHub={() => setIsModelHubOpen(true)}
        device={device}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Navigation Tabs */}
        <NavigationTabs
          currentTab={currentTab}
          onSelectTab={handleSelectTab}
          lang={lang}
          accentColor={accentColor}
        />

        {/* Tab Content */}
        {currentTab === 'library' ? (
          <LibraryView
            lang={lang}
            accentColor={accentColor}
            onLoadProject={handleLoadProject}
            onNotify={addToast}
          />
        ) : currentTab === 'leaderboard' ? (
          <LeaderboardView lang={lang} accentColor={accentColor} />
        ) : currentTab === 'batch' ? (
          <BatchProcessingView
            lang={lang}
            accentColor={accentColor}
            availableModels={availableModels}
            outputFormat={outputFormat}
            onNotify={addToast}
          />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-7 items-start">
            {/* Left Column: Upload Deck, Processing Status & Audio Players (8 cols) */}
            <div className="lg:col-span-7 xl:col-span-8 space-y-6">
              {/* Upload & Queue */}
              <UploadZone
                queue={queue}
                onAddToQueue={(newItems) => setQueue((prev) => [...prev, ...newItems])}
                onRemoveFromQueue={(id) => setQueue((prev) => prev.filter((item) => item.id !== id))}
                onClearQueue={() => setQueue([])}
                isProcessing={isProcessing}
                onStartSeparation={handleStartSeparation}
                lang={lang}
                accentColor={accentColor}
                onNotify={addToast}
              />

              {/* Live Processing Progress Bar */}
              {isProcessing && (
                <div className="glass-panel rounded-3xl p-6 shadow-2xl space-y-3 animate-pulse border border-white/15">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
                      <span className="text-sm font-bold font-outfit text-white">
                        {processingMessage || t('Separating Audio Tracks')}
                      </span>
                    </div>
                    <span className="text-sm font-mono font-bold text-indigo-400">{progress}%</span>
                  </div>

                  <div className="w-full bg-slate-950/80 h-3 rounded-full overflow-hidden border border-white/10 p-0.5">
                    <div
                      className={cn(
                        'h-full transition-all duration-300 rounded-full shadow-lg',
                        accentColor === 'indigo' && 'bg-gradient-to-r from-indigo-500 to-indigo-600 shadow-indigo-500/50',
                        accentColor === 'emerald' && 'bg-gradient-to-r from-emerald-500 to-emerald-600 shadow-emerald-500/50',
                        accentColor === 'rose' && 'bg-gradient-to-r from-rose-500 to-rose-600 shadow-rose-500/50',
                        accentColor === 'amber' && 'bg-gradient-to-r from-amber-500 to-amber-600 shadow-amber-500/50',
                        accentColor === 'violet' && 'bg-gradient-to-r from-violet-500 to-violet-600 shadow-violet-500/50'
                      )}
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Separated Stems Output Players */}
              {separatedStems.length > 0 && (
                <div id="separated-stems-section" className="space-y-4 pt-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                      <h3 className="text-base font-bold font-outfit text-white tracking-tight">
                        {t('Separated Stems')} ({separatedStems.length})
                      </h3>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {separatedStems.map((stem) => (
                      <StemAudioPlayer
                        key={stem}
                        stem={stem}
                        allStems={separatedStems}
                        lang={lang}
                        accentColor={accentColor}
                        onNewStemCreated={(newStem) =>
                          setSeparatedStems((prev) => [newStem, ...prev])
                        }
                        onNotify={addToast}
                      />
                    ))}
                  </div>

                  {/* Multi-Stem Studio Remix Web Audio Player */}
                  <StudioRemix
                    stems={separatedStems}
                    lang={lang}
                    accentColor={accentColor}
                    onNewRemixCreated={(remixFile) =>
                      setSeparatedStems((prev) => [remixFile, ...prev])
                    }
                    onNotify={addToast}
                  />
                </div>
              )}

              {/* Pro Tip Info Banner */}
              <div className="glass-panel p-4 rounded-2xl border border-white/5 flex items-center gap-3 text-xs text-slate-400 shadow-lg">
                <Info className="w-4 h-4 text-indigo-400 shrink-0" />
                <p>
                  <span className="font-bold text-slate-200">{t('Pro Tip')}:</span>{' '}
                  {t('BS-Roformer models usually provide the best vocal extraction results for modern pop and rock tracks.')}
                </p>
              </div>
            </div>

            {/* Right Column: Model Configuration Rack (4 cols) */}
            <div className="lg:col-span-5 xl:col-span-4 sticky top-24">
              <ModelConfiguration
                currentTab={currentTab}
                availableModels={availableModels}
                selectedModel={selectedModel}
                onSelectModel={setSelectedModel}
                outputFormat={outputFormat}
                onChangeOutputFormat={setOutputFormat}
                params={params}
                onChangeParams={setParams}
                ensembleMode={ensembleMode}
                onToggleEnsembleMode={() => setEnsembleMode(!ensembleMode)}
                ensembleSlots={ensembleSlots}
                onChangeEnsembleSlots={setEnsembleSlots}
                lang={lang}
                accentColor={accentColor}
                onNotify={addToast}
                onOpenModelHub={() => setIsModelHubOpen(true)}
              />
            </div>
          </div>
        )}
      </main>

      {/* Global Modals */}
      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        lang={lang}
        accentColor={accentColor}
        device={device}
        onChangeDevice={(newDev) => {
          setDevice(newDev);
          addToast('success', 'Settings Saved', `Compute device set to ${newDev}`);
        }}
        params={params}
        onChangeParams={setParams}
        onNotify={addToast}
      />

      <ModelDownloaderModal
        isOpen={isModelHubOpen}
        onClose={() => setIsModelHubOpen(false)}
        lang={lang}
        accentColor={accentColor}
        availableModels={availableModels}
        onNotify={addToast}
      />

      {/* Floating Notifications */}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
}
