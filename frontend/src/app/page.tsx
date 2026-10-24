'use client';

import { initializeProjects, projectStorage } from '@/lib/project-storage';

import React, { useState, useEffect, useCallback, useRef } from 'react';
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
import atlasStudioV2 from '@/lib/atlas-studio-v2-preset.json';
import { LocalStudioPanel } from '@/components/LocalStudioPanel';
import { Header } from '@/components/Header';
import { NavigationTabs } from '@/components/NavigationTabs';
import { UploadZone, UploadedItem } from '@/components/UploadZone';
import { ModelConfiguration } from '@/components/ModelConfiguration';
import { StemTransferModal, type StemPair } from '@/components/StemTransferModal';
import { StemAudioPlayer } from '@/components/StemAudioPlayer';
import { OriginalAudioPlayer } from '@/components/OriginalAudioPlayer';
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
  const [projectsReady,setProjectsReady]=useState(false);
  const [projectError,setProjectError]=useState('');
  const loadProjects=()=>{setProjectError('');void initializeProjects().then(()=>setProjectsReady(true)).catch(e=>setProjectError(e.message));};
  useEffect(loadProjects,[]);
  // Localization & Theme
  const [lang, setLang] = useState<Language>('tr');
  const [accentColor, setAccentColor] = useState<AccentColor>('indigo');

  useEffect(() => {
    try {
      const savedLang = projectStorage.getItem('uvr_lang') as Language;
      if (savedLang && (savedLang === 'tr' || savedLang === 'en')) setLang(savedLang);
      const savedAccent = projectStorage.getItem('uvr_accent') as AccentColor;
      if (savedAccent) setAccentColor(savedAccent);
    } catch {}
  }, [projectsReady]);

  const handleToggleLang = () => {
    const nextLang = lang === 'tr' ? 'en' : 'tr';
    setLang(nextLang);
    try {
      projectStorage.setItem('uvr_lang', nextLang);
    } catch {}
  };

  const handleChangeAccent = (color: AccentColor) => {
    setAccentColor(color);
    try {
      projectStorage.setItem('uvr_accent', color);
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
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const etaSamples = useRef<Array<{time:number;progress:number}>>([]);
  const etaDeadline = useRef<number | null>(null);
  useEffect(() => {
    if (!isProcessing) return;
    const timer = setInterval(() => {
      if (etaDeadline.current !== null) setRemainingSeconds(Math.max(1, Math.ceil((etaDeadline.current-Date.now())/1000)));
    }, 1000);
    return () => clearInterval(timer);
  }, [isProcessing]);
  const [separatedStems, setSeparatedStems] = useState<string[]>([]);
  const [transferSelection,setTransferSelection]=useState<{vocal:string;time:number}|null>(null);
  const applyStemTransfer=(before:StemPair,after:StemPair,time:number)=>{
    const replace=(stems:string[])=>stems.map(name=>name===before.vocal?after.vocal:name===before.instrumental?after.instrumental:name);
    for(const name of [after.vocal,after.instrumental])sessionStorage.setItem('uvr-restart-player:'+name,JSON.stringify({time,karaoke:false}));
    setSeparatedStems(replace);
    const library:LibraryItem[]=JSON.parse(projectStorage.getItem('uvr_library')||'[]');
    projectStorage.setItem('uvr_library',JSON.stringify(library.map(item=>item.stems.includes(before.vocal)&&item.stems.includes(before.instrumental)?{...item,stems:replace(item.stems)}:item)));
  };
  const [resultSource, setResultSource] = useState<{ name: string; path: string } | null>(null);
  const [activeProjectId,setActiveProjectId]=useState<number|null>(null);
  const restoredAfterRestart=useRef(false);
  useEffect(() => {
    const capture = () => sessionStorage.setItem('uvr-restart-workspace', JSON.stringify({
      currentTab, queue:queue.map(({id,name,path,size})=>({id,name,path,size})), separatedStems,
      resultSource, activeProjectId, params, selectedModel, ensembleMode, ensembleSlots,
      outputFormat, scrollY:window.scrollY,
    }));
    window.addEventListener('uvr-before-restart', capture);
    return () => window.removeEventListener('uvr-before-restart', capture);
  }, [currentTab,queue,separatedStems,resultSource,activeProjectId,params,selectedModel,ensembleMode,ensembleSlots,outputFormat]);
  useEffect(() => {
    if (!projectsReady) return;
    const saved = sessionStorage.getItem('uvr-restart-workspace');
    if (!saved) return;
    try {
      const state = JSON.parse(saved);
      restoredAfterRestart.current=true;
      setCurrentTab(state.currentTab); setQueue(state.queue); setSeparatedStems(state.separatedStems);
      setResultSource(state.resultSource); setActiveProjectId(state.activeProjectId);
      setParams(state.params); setSelectedModel(state.selectedModel); setEnsembleMode(state.ensembleMode);
      setEnsembleSlots(state.ensembleSlots); setOutputFormat(state.outputFormat);
      setTimeout(()=>window.scrollTo({top:state.scrollY || 0}),500);
      sessionStorage.removeItem('uvr-restart-workspace');
    } catch { sessionStorage.removeItem('uvr-restart-workspace'); }
  }, [projectsReady]);

  useEffect(()=>{
    if(!projectsReady||activeProjectId===null||!['roformer','mdx23c','mdxnet','vrarch','demucs'].includes(currentTab))return;
    const library:LibraryItem[]=JSON.parse(projectStorage.getItem('uvr_library')||'[]');
    const settings={params,model:selectedModel,tab:currentTab,ensembleMode,ensembleSlots,format:outputFormat};
    const updated=library.map(item=>item.id===activeProjectId?{...item,settings}:item);
    if(JSON.stringify(updated)!==JSON.stringify(library))projectStorage.setItem('uvr_library',JSON.stringify(updated));
  },[projectsReady,activeProjectId,params,selectedModel,currentTab,ensembleMode,ensembleSlots,outputFormat]);

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
        if(restoredAfterRestart.current)return;
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
    etaSamples.current = [];
    etaDeadline.current = null;
    setRemainingSeconds(null);
    setProgress(10);
    setProcessingMessage('Initializing AI neural network models...');
    setSeparatedStems([]);
    setResultSource(null);

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
      let reconnectFailures = 0;
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await api.getTaskStatus(taskId);
          reconnectFailures = 0;
          const rawProg = statusRes.progress ?? 0.1;
          const pct = Math.round(rawProg <= 1.0 ? rawProg * 100 : rawProg);
          const measuredPct = rawProg <= 1 ? rawProg * 100 : rawProg;
          const samples = etaSamples.current;
          if (!samples.length || measuredPct > samples[samples.length-1].progress) {
            samples.push({time:Date.now(),progress:measuredPct});
            if (samples.length > 30) samples.shift();
            const first = samples[0], last = samples[samples.length-1];
            if (last.time-first.time >= 10000 && last.progress > first.progress) {
              const seconds = (100-last.progress)*(last.time-first.time)/(last.progress-first.progress)/1000;
              etaDeadline.current = Date.now()+seconds*1000;
              setRemainingSeconds(Math.max(1,Math.ceil(seconds)));
            }
          }
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
            setResultSource({ name: currentItem.name, path: currentItem.path });
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
                projectStorage.getItem('uvr_library') || '[]'
              );
              const newEntry: LibraryItem = {
                id: Date.now(),
                filename: currentItem.name,
                source_path: currentItem.path,
                stems,
                timestamp: new Date().toLocaleTimeString(),
                settings:{params,model:selectedModel,tab:currentTab,ensembleMode,ensembleSlots,format:outputFormat},
              };
              setActiveProjectId(newEntry.id);
              const updatedLib = [newEntry, ...prevLib];
              projectStorage.setItem('uvr_library', JSON.stringify(updatedLib));
            } catch (err) {
              console.error(err);
            }
          } else if (statusRes.status === 'failed') {
            clearInterval(pollInterval);
            setIsProcessing(false);
            addToast('error', 'Separation Failed', statusRes.error || statusRes.message);
          }
        } catch (err: any) {
          reconnectFailures += 1;
          setProcessingMessage('Sunucu bağlantısı bekleniyor; kayıtlı parçalar korunuyor...');
          if (reconnectFailures >= 150) {
            clearInterval(pollInterval);
            setIsProcessing(false);
            addToast('error', 'Bağlantı kesildi', 'Sunucuyu yeniden açın. Ayrıştırma kayıtlı parçalarından devam edecek.');
          }
        }
      }, 1200);
    } catch (e: any) {
      setIsProcessing(false);
      addToast('error', 'Error starting separation', e.message);
    }
  };

  // Load Project Session from Library (PSD Style)
  const handleLoadProject = (project: LibraryItem) => {
    setActiveProjectId(project.id);
    // 1. Set Queue with loaded file
    const loadedItem: UploadedItem = {
      id: `${project.id || Date.now()}`,
      name: project.filename,
      path: project.source_path || project.filename,
      size: 0,
    };
    setQueue([loadedItem]);

    // 2. Restore separated stems
    setSeparatedStems(project.stems || []);
    setResultSource({ name: project.filename, path: project.source_path || project.filename });

    // 3. Switch back to studio workspace tab
    setCurrentTab(project.settings?.tab||'roformer');
    if(project.settings){
      const settings=project.settings;
      const slots=settings.params.ensemble_profile==='atlas_studio_v2'
        ? atlasStudioV2.models.map(({model_type,model_key})=>({model_type,model_key}))
        : settings.ensembleSlots;
      setParams(settings.params);setSelectedModel(settings.model);setEnsembleMode(settings.ensembleMode);
      setEnsembleSlots(slots);setOutputFormat(settings.format);
    }

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

  if(!projectsReady)return <div className="min-h-screen bg-[#17141f] text-slate-200 flex items-center justify-center"><div role="status">{projectError||'Yerel projeler yükleniyor…'}{projectError&&<button className="ml-4 rounded-xl border border-violet-300/30 p-3" onClick={loadProjects}>Tekrar dene</button>}</div></div>;
  return (
    <div className="min-h-screen studio-shell text-slate-100 flex flex-col selection:bg-indigo-500/30 font-sans">
      <Header
        lang={lang}
        accentColor={accentColor}
        onToggleLang={handleToggleLang}
        onChangeAccent={handleChangeAccent}
        onOpenSettings={() => setShowSettings(true)}
        onOpenModelHub={() => setIsModelHubOpen(true)}
        device={device}
      />

      <main className="flex-1 max-w-[1840px] w-full mx-auto px-4 sm:px-6 lg:px-10 py-8 space-y-8">
        <section className="flex flex-wrap items-center justify-between gap-4 px-1">
          <div><p className="text-xs font-semibold tracking-[0.16em] uppercase text-indigo-300 mb-2">{lang==='tr'?'Senin küçük müzik atölyen':'Your little music studio'}</p>
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight font-outfit">{lang==='tr'?'Müziğine yer aç.':'Make room for your music.'}</h2>
          <p className="mt-2 text-sm sm:text-base text-slate-400">{lang==='tr'?'Sesini ayır, yeniden karıştır ve birlikte söyle.':'Separate, remix, and sing along.'}</p></div>
          <span aria-hidden="true" className="hidden sm:flex items-center gap-3 rounded-full border border-indigo-300/15 bg-indigo-400/10 px-5 py-3 text-indigo-200"><Music className="h-5 w-5"/><Sparkles className="h-4 w-4 text-rose-300"/></span>
        </section>
        <LocalStudioPanel />
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
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 items-start">
            {/* Left Column: Upload Deck, Processing Status & Audio Players (8 cols) */}
            <div className="xl:col-span-7 2xl:col-span-8 space-y-6">
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

                  <p className="text-xs text-indigo-200 tabular-nums" role="status">
                    {remainingSeconds === null ? 'Kalan süre hesaplanıyor · İşlem hızı ölçülüyor' : `Tahmini kalan süre: ${Math.floor(remainingSeconds/60)} dk ${remainingSeconds%60} sn · İşlem hızına göre güncellenir`}
                  </p>
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
                      <Music className="w-4 h-4 text-slate-400" />
                      <h3 className="text-base font-bold font-outfit text-white tracking-tight">
                        {lang === 'tr' ? 'Dinle ve karşılaştır' : 'Listen and compare'}
                      </h3>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {resultSource && (
                      <OriginalAudioPlayer key={resultSource.path} source={resultSource} lang={lang} accentColor={accentColor} />
                    )}
                    {[...separatedStems].sort((a, b) => {
                      const rank = (name: string) => /vocal|vox/i.test(name) ? 0 : /instrumental|inst|other/i.test(name) ? 1 : 2;
                      return rank(a) - rank(b);
                    }).map((stem) => (
                      <StemAudioPlayer
                        key={stem}
                        stem={stem}
                        allStems={separatedStems}
                        onTransferRequested={/vocal|vox/i.test(stem)&&separatedStems.some(name=>/instrumental|\(instrument\)|\(other\)/i.test(name))?(time)=>setTransferSelection({vocal:stem,time}):undefined}
                        lang={lang}
                        accentColor={accentColor}
                        onNewStemCreated={(newStem) => {
                          setSeparatedStems((prev) => [newStem, ...prev]);
                          const library:LibraryItem[]=JSON.parse(projectStorage.getItem('uvr_library')||'[]');
                          const updated=library.map(item=>item.stems.includes(stem)?{...item,stems:[...new Set([newStem,...item.stems])]}:item);
                          projectStorage.setItem('uvr_library',JSON.stringify(updated));
                        }}
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
            <div className="xl:col-span-5 2xl:col-span-4 xl:sticky xl:top-24">
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

      {transferSelection&&<StemTransferModal vocal={transferSelection.vocal} initialTime={transferSelection.time} instrumentals={separatedStems.filter(name=>/instrumental|\(instrument\)|\(other\)/i.test(name))} onClose={()=>setTransferSelection(null)} onApply={applyStemTransfer}/>}

      {/* Floating Notifications */}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
}
