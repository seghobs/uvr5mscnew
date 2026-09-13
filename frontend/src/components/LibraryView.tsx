'use client';

import { projectStorage } from '@/lib/project-storage';

import React, { useState, useEffect, useRef } from 'react';
import { Language, AccentColor, LibraryItem } from '@/lib/types';
import { cn, formatTime } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';
import {
  FolderHeart,
  Music,
  Trash2,
  Download,
  Play,
  Pause,
  Disc,
  Volume2,
  VolumeX,
  RotateCcw,
  FastForward,
  Rewind,
  Sparkles,
  Sliders,
  Check,
  FolderOpen,
  FileCode,
  Upload,
} from 'lucide-react';

interface LibraryViewProps {
  lang: Language;
  accentColor: AccentColor;
  onLoadProject?: (item: LibraryItem) => void;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const LibraryView: React.FC<LibraryViewProps> = ({
  lang,
  accentColor,
  onLoadProject,
  onNotify,
}) => {
  const t = (key: string) => getTranslation(lang, key);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [library, setLibrary] = useState<LibraryItem[]>(() => {
    if (typeof window !== 'undefined') {
      try {
        const stored = projectStorage.getItem('uvr_library');
        return stored ? JSON.parse(stored) : [];
      } catch {
        return [];
      }
    }
    return [];
  });

  useEffect(()=>{const refresh=(event:Event)=>{if((event as CustomEvent).detail?.key==='uvr_library'){try{setLibrary(JSON.parse(projectStorage.getItem('uvr_library')||'[]'));}catch{}}};window.addEventListener('uvr-project-changed',refresh);return()=>window.removeEventListener('uvr-project-changed',refresh);},[]);

  const exportProjectFile = (item: LibraryItem) => {
    const jsonStr = JSON.stringify(item, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${item.filename.replace(/\.[^/.]+$/, '')}.uvrproj`;
    a.click();
    URL.revokeObjectURL(url);
    onNotify('success', 'Proje Dışa Aktarıldı', '.uvrproj oturum dosyası kaydedildi.');
  };

  const handleImportProjectFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const project = JSON.parse(ev.target?.result as string) as LibraryItem;
        if (!project.filename || !Array.isArray(project.stems)) {
          throw new Error('Geçersiz proje formatı');
        }
        // Add to library if not exists
        setLibrary((prev) => {
          const updated = [project, ...prev.filter((p) => p.id !== project.id)];
          projectStorage.setItem('uvr_library', JSON.stringify(updated));
          return updated;
        });
        onNotify('success', 'Proje İçe Aktarıldı', `"${project.filename}" kütüphaneye eklendi.`);
        if (onLoadProject) {
          onLoadProject(project);
        }
      } catch (err: any) {
        onNotify('error', 'İçe Aktarma Başarısız', err.message || 'Geçersiz .uvrproj dosyası');
      }
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const [activeStem, setActiveStem] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const progressTrackRef = useRef<HTMLDivElement>(null);

  // Initialize and attach audio listeners
  useEffect(() => {
    const audio = new Audio();
    audioRef.current = audio;

    const onTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
    };
    const onLoadedMetadata = () => {
      setDuration(audio.duration || 0);
    };
    const onEnded = () => {
      setIsPlaying(false);
      setCurrentTime(0);
    };
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('loadedmetadata', onLoadedMetadata);
    audio.addEventListener('ended', onEnded);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('loadedmetadata', onLoadedMetadata);
      audio.removeEventListener('ended', onEnded);
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
      audio.pause();
      audio.src = '';
    };
  }, []);

  const togglePlayStem = (stem: string) => {
    const audio = audioRef.current;
    if (!audio) return;

    if (activeStem === stem) {
      if (isPlaying) {
        audio.pause();
      } else {
        audio.play().catch(() => {});
      }
    } else {
      audio.pause();
      audio.src = `/output/${encodeURIComponent(stem)}`;
      audio.load();
      audio.play().catch(() => {});
      setActiveStem(stem);
      setCurrentTime(0);
    }
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    const track = progressTrackRef.current;
    if (!audio || !track || !duration) return;

    const rect = track.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percent = Math.max(0, Math.min(1, clickX / rect.width));
    const newTime = percent * duration;
    audio.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const handleSkip = (seconds: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    const nextTime = Math.max(0, Math.min(duration, audio.currentTime + seconds));
    audio.currentTime = nextTime;
    setCurrentTime(nextTime);
  };

  const handleVolumeChange = (newVol: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    setVolume(newVol);
    audio.volume = newVol;
    if (newVol > 0 && isMuted) {
      setIsMuted(false);
      audio.muted = false;
    }
  };

  const toggleMute = () => {
    const audio = audioRef.current;
    if (!audio) return;
    const nextMuted = !isMuted;
    setIsMuted(nextMuted);
    audio.muted = nextMuted;
  };

  const handleDeleteItem = (id: number) => {
    const updated = library.filter((item) => item.id !== id);
    setLibrary(updated);
    try {
      projectStorage.setItem('uvr_library', JSON.stringify(updated));
    } catch {}
    onNotify('info', 'Item Removed', 'Removed from library history');
  };

  const handleClearAll = () => {
    if (confirm('Kütüphanedeki tüm işlem geçmişini silmek istediğinize emin misiniz?')) {
      setLibrary([]);
      try {
        projectStorage.removeItem('uvr_library');
      } catch {}
      if (audioRef.current) {
        audioRef.current.pause();
      }
      setActiveStem(null);
      onNotify('info', 'Library Cleared', 'All history deleted');
    }
  };

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="glass-panel rounded-3xl p-6 sm:p-8 lg:p-8 shadow-2xl space-y-6 border border-white/10">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-2xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 shadow-[0_0_15px_rgba(99,102,241,0.2)]">
            <FolderHeart className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xl font-black font-outfit text-white tracking-tight">
                {t('Library')}
              </h3>
              <span className="text-[10px] font-mono font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/20">
                PROJE OTURUMLARI
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Kayıtlı çalışmalarınızı Photoshop PSD gibi yükleyip kaldığınız yerden devam edin.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
          {/* Import Project (.uvrproj) Button */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleImportProjectFile}
            accept=".uvrproj,.json"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-3.5 py-2 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold transition-all flex items-center gap-1.5 active:scale-95 shadow-md shadow-indigo-500/10"
            title="Daha önce dışa aktarılmış bir .uvrproj oturum dosyasını yükleyin"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>📥 Proje Aç (.uvrproj)</span>
          </button>

          {library.length > 0 && (
            <button
              onClick={handleClearAll}
              className="px-3.5 py-2 rounded-xl bg-white/[0.04] hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 border border-white/5 hover:border-rose-500/30 text-xs font-bold transition-all flex items-center gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Tümünü Temizle</span>
            </button>
          )}
        </div>
      </div>

      {/* Advanced Active Audio Player Dock (Fixed in Library when Playing) */}
      {activeStem && (
        <div className="p-4 sm:p-5 rounded-2xl glass-panel border border-indigo-500/30 shadow-2xl bg-gradient-to-r from-indigo-950/40 via-slate-900/60 to-purple-950/40 space-y-3 relative overflow-hidden animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            {/* Playing Stem Title */}
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/40 flex items-center justify-center shrink-0 shadow-lg">
                <Disc className={cn('w-5 h-5', isPlaying && 'animate-spin-slow')} />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    Oynatılıyor
                  </span>
                  <span className="text-xs font-bold text-white truncate">{activeStem}</span>
                </div>
                <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                  {formatTime(currentTime)} / {formatTime(duration)}
                </div>
              </div>
            </div>

            {/* Quick Player Controls */}
            <div className="flex items-center gap-2 self-center sm:self-auto">
              <button
                onClick={() => handleSkip(-5)}
                className="p-2 rounded-xl bg-white/[0.05] hover:bg-white/10 text-slate-300 hover:text-white transition-all active:scale-95"
                title="5 saniye geri"
              >
                <Rewind className="w-4 h-4" />
              </button>

              <button
                onClick={() => activeStem && togglePlayStem(activeStem)}
                className="w-11 h-11 rounded-xl bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white flex items-center justify-center transition-all shadow-lg shadow-indigo-500/30 active:scale-90"
              >
                {isPlaying ? (
                  <Pause className="w-5 h-5 fill-white" />
                ) : (
                  <Play className="w-5 h-5 fill-white ml-0.5" />
                )}
              </button>

              <button
                onClick={() => handleSkip(5)}
                className="p-2 rounded-xl bg-white/[0.05] hover:bg-white/10 text-slate-300 hover:text-white transition-all active:scale-95"
                title="5 saniye ileri"
              >
                <FastForward className="w-4 h-4" />
              </button>

              {/* Volume Slider */}
              <div className="hidden md:flex items-center gap-2 pl-2 border-l border-white/10">
                <button
                  onClick={toggleMute}
                  className="p-2 rounded-xl hover:bg-white/5 text-slate-400 hover:text-white transition-colors"
                >
                  {isMuted || volume === 0 ? (
                    <VolumeX className="w-4 h-4 text-rose-400" />
                  ) : (
                    <Volume2 className="w-4 h-4" />
                  )}
                </button>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={isMuted ? 0 : volume}
                  onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                  className="w-20 accent-indigo-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                />
              </div>

              {/* Direct Download */}
              <a
                href={`/output/${encodeURIComponent(activeStem)}`}
                download={activeStem}
                className="p-2.5 rounded-xl bg-white/[0.05] hover:bg-white/10 text-slate-300 hover:text-white border border-white/10 transition-colors ml-1"
                title="İndir"
              >
                <Download className="w-4 h-4" />
              </a>
            </div>
          </div>

          {/* Interactive Scrubbing Progress Track */}
          <div
            ref={progressTrackRef}
            onClick={handleSeek}
            className="w-full h-3.5 bg-slate-950/80 rounded-full cursor-pointer relative group overflow-hidden border border-white/10 p-0.5"
          >
            <div
              className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-400 rounded-full transition-all duration-100 shadow-[0_0_12px_rgba(99,102,241,0.5)] relative"
              style={{ width: `${progressPercent}%` }}
            >
              <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-md scale-0 group-hover:scale-100 transition-transform" />
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {library.length === 0 ? (
        <div className="p-14 text-center border-2 border-dashed border-white/10 rounded-3xl space-y-3 glass-panel">
          <Disc className="w-12 h-12 text-slate-600 mx-auto animate-spin-slow" />
          <h4 className="text-sm font-bold text-slate-300">
            {t('No processed files in your library yet.')}
          </h4>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Roformer, MDX veya Demucs kullanarak ses ayrıştırdığınızda tüm kanallar otomatik olarak burada listelenecektir.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {library.map((item) => (
            <div
              key={item.id}
              className="p-5 rounded-2xl glass-panel border border-white/10 space-y-4 hover:border-white/20 transition-all shadow-lg"
            >
              {/* File Info Bar & Session Actions */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-white/5">
                <div className="flex items-center gap-3 truncate">
                  <div className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse shadow-[0_0_8px_rgba(99,102,241,0.6)] shrink-0" />
                  <span className="font-black text-sm text-white truncate font-outfit">
                    {item.filename}
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 bg-white/[0.04] px-2 py-0.5 rounded-md border border-white/5 shrink-0">
                    {item.timestamp}
                  </span>
                  <span className="hidden md:inline-block text-[10px] font-mono text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded-md border border-indigo-500/20 shrink-0">
                    {item.stems.length} STEM
                  </span>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-auto">
                  {/* Load Project Session Button (PSD Style) */}
                  {onLoadProject && (
                    <button
                      onClick={() => onLoadProject(item)}
                      className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-500 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-xs shadow-lg shadow-indigo-600/20 active:scale-95 transition-all flex items-center gap-1.5"
                      title="Bu projeyi çalışma alanına geri yükle ve mikserde düzenle"
                    >
                      <FolderOpen className="w-3.5 h-3.5" />
                      <span>Projeyi Yükle</span>
                    </button>
                  )}

                  {/* Export Project File (.uvrproj) */}
                  <button
                    onClick={() => exportProjectFile(item)}
                    className="p-1.5 rounded-xl bg-white/[0.04] hover:bg-white/10 text-slate-400 hover:text-indigo-300 border border-white/5 transition-colors"
                    title="Projeyi .uvrproj oturum dosyası olarak kaydet"
                  >
                    <FileCode className="w-4 h-4" />
                  </button>

                  {/* Delete from History */}
                  <button
                    onClick={() => handleDeleteItem(item.id)}
                    className="p-1.5 rounded-xl hover:bg-rose-500/15 text-slate-500 hover:text-rose-400 transition-colors border border-transparent hover:border-rose-500/20"
                    title="Geçmişten Sil"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Stems Cards with Mini Progress & Seek */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {item.stems.map((stem) => {
                  const isCurrent = activeStem === stem;
                  const isCurrentPlaying = isCurrent && isPlaying;
                  const isVocal = stem.toLowerCase().includes('vocal') || stem.toLowerCase().includes('vok');
                  const isInst =
                    stem.toLowerCase().includes('instrumental') ||
                    stem.toLowerCase().includes('inst') ||
                    stem.toLowerCase().includes('other');

                  return (
                    <div
                      key={stem}
                      className={cn(
                        'p-3.5 rounded-2xl border flex flex-col justify-between gap-3 text-xs transition-all duration-200 shadow-md relative overflow-hidden group',
                        isCurrent
                          ? 'bg-gradient-to-br from-indigo-950/80 to-slate-900/90 border-indigo-500/50 text-white shadow-indigo-500/10'
                          : 'bg-slate-900/70 hover:bg-slate-900 border-white/10 text-slate-300 hover:border-white/20'
                      )}
                    >
                      {/* Stem Header & Badge */}
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2.5 truncate">
                          <button
                            onClick={() => togglePlayStem(stem)}
                            className={cn(
                              'w-8 h-8 rounded-xl flex items-center justify-center transition-all shrink-0 active:scale-90 shadow-md',
                              isCurrentPlaying
                                ? 'bg-indigo-500 text-white shadow-indigo-500/40'
                                : 'bg-slate-800 hover:bg-slate-700 text-slate-200'
                            )}
                          >
                            {isCurrentPlaying ? (
                              <Pause className="w-4 h-4 fill-white" />
                            ) : (
                              <Play className="w-4 h-4 fill-white ml-0.5" />
                            )}
                          </button>
                          <span className="font-bold truncate text-xs text-white" title={stem}>
                            {stem}
                          </span>
                        </div>

                        <a
                          href={`/output/${encodeURIComponent(stem)}`}
                          download={stem}
                          className="p-2 rounded-xl bg-white/[0.04] hover:bg-white/10 text-slate-400 hover:text-white transition-colors shrink-0"
                          title="İndir"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
