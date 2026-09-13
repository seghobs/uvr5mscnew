'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  UploadCloud,
  Link as LinkIcon,
  Search,
  Music,
  X,
  Play,
  Pause,
  Loader2,
  CheckCircle2,
  Youtube,
  Radio,
  FileAudio,
  Sparkles,
  Download,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { Language, AccentColor, SearchResult } from '@/lib/types';
import { cn, formatBytes, formatTime } from '@/lib/utils';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';

export interface UploadedItem {
  id: string;
  name: string;
  size?: number;
  path: string;
  file?: File;
}

interface UploadZoneProps {
  queue: UploadedItem[];
  onAddToQueue: (items: UploadedItem[]) => void;
  onRemoveFromQueue: (id: string) => void;
  onClearQueue: () => void;
  isProcessing: boolean;
  onStartSeparation: () => void;
  lang: Language;
  accentColor: AccentColor;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string) => void;
}

export const UploadZone: React.FC<UploadZoneProps> = ({
  queue,
  onAddToQueue,
  onRemoveFromQueue,
  onClearQueue,
  isProcessing,
  onStartSeparation,
  lang,
  accentColor,
  onNotify,
}) => {
  const t = (key: string) => getTranslation(lang, key);
  const [isDragOver, setIsDragOver] = useState(false);
  const [inputVal, setInputVal] = useState('');
  const [isDownloadingUrl, setIsDownloadingUrl] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const [searchLimit, setSearchLimit] = useState(15);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  // YouTube Audio Preview Player State
  const [playingVideoId, setPlayingVideoId] = useState<string | null>(null);
  const [playingResult, setPlayingResult] = useState<SearchResult | null>(null);
  const [isPlayingPreview, setIsPlayingPreview] = useState(false);
  const [isBufferingPreview, setIsBufferingPreview] = useState(false);
  const [previewCurrentTime, setPreviewCurrentTime] = useState(0);
  const [previewDuration, setPreviewDuration] = useState(0);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastQueryRef = useRef<string>('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const ytPlayerRef = useRef<any>(null);
  const isYtReadyRef = useRef<boolean>(false);
  const previewTimerRef = useRef<NodeJS.Timeout | null>(null);

  const extractVideoId = (item: SearchResult): string | null => {
    if (item.id) return item.id;
    if (!item.url) return null;
    const match = item.url.match(/(?:youtu\.be\/|v=|\/embed\/|\/v\/|watch\?v=)([\w-]{11})/);
    return match ? match[1] : null;
  };

  const isUrl = (text: string) => {
    const trimmed = text.trim();
    return /^(https?:\/\/|www\.|youtube\.com|youtu\.be|soundcloud\.com|spotify\.com)/i.test(trimmed);
  };

  // Initialize YouTube Iframe API
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const initPlayer = () => {
      const win = window as any;
      const target = document.getElementById('yt-hidden-preview-player');
      if (win.YT && win.YT.Player && !ytPlayerRef.current && target) {
        try {
          ytPlayerRef.current = new win.YT.Player('yt-hidden-preview-player', {
            height: '1',
            width: '1',
            playerVars: {
              autoplay: 0,
              controls: 0,
              disablekb: 1,
              fs: 0,
              modestbranding: 1,
              playsinline: 1,
              rel: 0,
            },
            events: {
              onReady: () => {
                isYtReadyRef.current = true;
              },
              onStateChange: (event: any) => {
                // 1 = PLAYING, 2 = PAUSED, 3 = BUFFERING, 0 = ENDED
                if (event.data === 1) {
                  setIsPlayingPreview(true);
                  setIsBufferingPreview(false);
                  const dur = ytPlayerRef.current?.getDuration?.() || 0;
                  if (dur > 0) setPreviewDuration(dur);
                } else if (event.data === 2) {
                  setIsPlayingPreview(false);
                  setIsBufferingPreview(false);
                } else if (event.data === 3) {
                  setIsBufferingPreview(true);
                } else if (event.data === 0) {
                  setIsPlayingPreview(false);
                  setIsBufferingPreview(false);
                  setPreviewCurrentTime(0);
                }
              },
              onError: (err: any) => {
                setIsBufferingPreview(false);
                setIsPlayingPreview(false);
              },
            },
          });
        } catch (e) {
          // ignore
        }
      }
    };

    const win = window as any;
    if (!win.YT) {
      const tag = document.createElement('script');
      tag.src = 'https://www.youtube.com/iframe_api';
      const firstScriptTag = document.getElementsByTagName('script')[0];
      firstScriptTag?.parentNode?.insertBefore(tag, firstScriptTag);
      win.onYouTubeIframeAPIReady = () => {
        initPlayer();
      };
    } else if (win.YT && win.YT.Player) {
      initPlayer();
    }

    return () => {
      if (previewTimerRef.current) clearInterval(previewTimerRef.current);
    };
  }, []);

  // Update preview playback timeline timer
  useEffect(() => {
    if (isPlayingPreview) {
      previewTimerRef.current = setInterval(() => {
        if (ytPlayerRef.current?.getCurrentTime && isYtReadyRef.current) {
          const cur = ytPlayerRef.current.getCurrentTime() || 0;
          setPreviewCurrentTime(cur);
          const dur = ytPlayerRef.current.getDuration?.() || 0;
          if (dur > 0) setPreviewDuration(dur);
        }
      }, 250);
    } else {
      if (previewTimerRef.current) clearInterval(previewTimerRef.current);
    }
    return () => {
      if (previewTimerRef.current) clearInterval(previewTimerRef.current);
    };
  }, [isPlayingPreview]);

  const togglePlayPreview = (res: SearchResult, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const vidId = extractVideoId(res);
    if (!vidId) return;

    if (playingVideoId === vidId) {
      if (isPlayingPreview) {
        if (isYtReadyRef.current) ytPlayerRef.current?.pauseVideo?.();
      } else {
        if (isYtReadyRef.current) ytPlayerRef.current?.playVideo?.();
      }
    } else {
      setPlayingVideoId(vidId);
      setPlayingResult(res);
      setPreviewCurrentTime(0);
      setIsBufferingPreview(true);
      setIsPlayingPreview(true);

      const doLoad = () => {
        if (isYtReadyRef.current && ytPlayerRef.current?.loadVideoById) {
          ytPlayerRef.current.loadVideoById({ videoId: vidId });
          ytPlayerRef.current.playVideo?.();
        }
      };

      if (isYtReadyRef.current && ytPlayerRef.current?.loadVideoById) {
        doLoad();
      } else {
        setTimeout(doLoad, 600);
      }
    }
  };

  const handleSeekPreview = (fraction: number, e: React.MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    if (!ytPlayerRef.current || previewDuration <= 0) return;
    const targetSeconds = fraction * previewDuration;
    ytPlayerRef.current.seekTo?.(targetSeconds, true);
    setPreviewCurrentTime(targetSeconds);
  };

  const stopPreview = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      if (ytPlayerRef.current) {
        if (typeof ytPlayerRef.current.stopVideo === 'function') ytPlayerRef.current.stopVideo();
        if (typeof ytPlayerRef.current.pauseVideo === 'function') ytPlayerRef.current.pauseVideo();
      }
    } catch {}
    setPlayingVideoId(null);
    setPlayingResult(null);
    setIsPlayingPreview(false);
    setIsBufferingPreview(false);
    setPreviewCurrentTime(0);
  };

  const closeAndClearSearch = () => {
    stopPreview();
    setShowSearchDropdown(false);
    setSearchResults([]);
    setIsSearching(false);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
  };

  // Close dropdown on click outside or ESC and stop preview & clear results
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        closeAndClearSearch();
      }
    };

    const handleGlobalKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeAndClearSearch();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleGlobalKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleGlobalKeyDown);
      stopPreview();
    };
  }, []);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const items: UploadedItem[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        const res = await api.uploadAudio(file);
        items.push({
          id: `${Date.now()}-${i}`,
          name: file.name,
          size: file.size,
          path: res.path,
          file,
        });
      } catch (e: any) {
        onNotify('error', 'Upload Failed', file.name + ': ' + (e.message || 'Unknown error'));
      }
    }

    if (items.length > 0) {
      onAddToQueue(items);
      onNotify('success', `${items.length} ${t('files added to queue')}`);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleUrlDownload = async (targetUrl?: string) => {
    const urlToDownload = (targetUrl || inputVal).trim();
    if (!urlToDownload) return;
    setIsDownloadingUrl(true);
    setShowSearchDropdown(false);
    try {
      const res = await api.downloadFromUrl(urlToDownload);
      onAddToQueue([
        {
          id: `${Date.now()}`,
          name: res.title || res.filename,
          path: res.path,
        },
      ]);
      setInputVal('');
      setSearchResults([]);
      onNotify('success', 'Download Complete', res.title || res.filename);
    } catch (e: any) {
      onNotify('error', 'Download Failed', e.message || 'Could not fetch audio from URL');
    } finally {
      setIsDownloadingUrl(false);
    }
  };

  const executeSearch = async (queryText: string, limit = 15) => {
    const trimmed = queryText.trim();
    if (!trimmed || trimmed.length < 2 || isUrl(trimmed)) {
      setSearchResults([]);
      setShowSearchDropdown(false);
      setIsSearching(false);
      return;
    }

    lastQueryRef.current = trimmed;
    setSearchLimit(limit);
    setIsSearching(true);

    try {
      const res = await api.search(trimmed, limit);
      // Ensure this response matches the very latest query
      if (lastQueryRef.current === trimmed) {
        const list = Array.isArray(res) ? res : [];
        setSearchResults(list);
        setShowSearchDropdown(list.length > 0);
        setHasMore(list.length >= limit && limit < 45);
      }
    } catch (e) {
      if (lastQueryRef.current === trimmed) {
        console.error('YouTube search error:', e);
        setSearchResults([]);
      }
    } finally {
      if (lastQueryRef.current === trimmed) {
        setIsSearching(false);
      }
    }
  };

  const loadMoreResults = async () => {
    if (isLoadingMore || !hasMore || isSearching || !inputVal.trim() || isUrl(inputVal)) return;
    const nextLimit = Math.min(45, searchLimit + 12);
    if (nextLimit === searchLimit) {
      setHasMore(false);
      return;
    }

    setIsLoadingMore(true);
    try {
      const res = await api.search(inputVal.trim(), nextLimit);
      if (lastQueryRef.current === inputVal.trim()) {
        const list = Array.isArray(res) ? res : [];
        setSearchResults(list);
        setSearchLimit(nextLimit);
        setHasMore(list.length >= nextLimit && nextLimit < 45);
      }
    } catch (e) {
      console.error('Failed to load more results:', e);
    } finally {
      setIsLoadingMore(false);
    }
  };

  const handleInputChange = (value: string) => {
    setInputVal(value);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);

    const trimmed = value.trim();
    if (isUrl(trimmed)) {
      setShowSearchDropdown(false);
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    if (!trimmed || trimmed.length < 2) {
      setSearchResults([]);
      setShowSearchDropdown(false);
      setIsSearching(false);
      return;
    }

    // Debounce for 450ms
    searchTimeoutRef.current = setTimeout(() => {
      executeSearch(trimmed, 15);
    }, 450);
  };

  const handleImmediateSearch = () => {
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    const trimmed = inputVal.trim();
    if (isUrl(trimmed)) {
      handleUrlDownload(trimmed);
    } else {
      executeSearch(trimmed, 15);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const trimmed = inputVal.trim();
      if (!trimmed) return;
      if (isUrl(trimmed)) {
        handleUrlDownload(trimmed);
      } else {
        handleImmediateSearch();
      }
    } else if (e.key === 'Escape') {
      closeAndClearSearch();
    }
  };

  const handleClearInput = () => {
    closeAndClearSearch();
    setInputVal('');
    lastQueryRef.current = '';
  };

  const selectSearchResult = async (result: SearchResult) => {
    stopPreview();
    setShowSearchDropdown(false);
    setSearchResults([]);
    setInputVal(result.title);
    setIsDownloadingUrl(true);
    try {
      const res = await api.downloadFromUrl(result.url);
      onAddToQueue([
        {
          id: `${Date.now()}`,
          name: result.title || res.filename,
          path: res.path,
        },
      ]);
      setInputVal('');
      setSearchResults([]);
      onNotify('success', 'Download Complete', result.title);
    } catch (e: any) {
      onNotify('error', 'Download Failed', e.message || 'Could not fetch YouTube video');
    } finally {
      setIsDownloadingUrl(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Immersive Studio Drag & Drop Deck */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          'relative p-10 sm:p-14 rounded-3xl border-2 border-dashed transition-all duration-300 cursor-pointer text-center group flex flex-col items-center justify-center overflow-hidden',
          isDragOver
            ? 'border-indigo-400 bg-indigo-500/15 scale-[1.01] shadow-[0_0_50px_rgba(99,102,241,0.25)]'
            : 'border-white/10 hover:border-white/20 glass-panel hover:bg-slate-900/60 shadow-2xl'
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="audio/*"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />

        {/* Clean Static Upload Icon */}
        <div
          className={cn(
            'w-16 h-16 rounded-2xl flex items-center justify-center mb-4 transition-transform duration-300 group-hover:scale-105 shadow-xl',
            accentColor === 'indigo' &&
              'bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 shadow-indigo-500/10',
            accentColor === 'emerald' &&
              'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shadow-emerald-500/10',
            accentColor === 'rose' &&
              'bg-rose-500/15 text-rose-400 border border-rose-500/30 shadow-rose-500/10',
            accentColor === 'amber' &&
              'bg-amber-500/15 text-amber-400 border border-amber-500/30 shadow-amber-500/10',
            accentColor === 'violet' &&
              'bg-violet-500/15 text-violet-400 border border-violet-500/30 shadow-violet-500/10'
          )}
        >
          <UploadCloud className="w-8 h-8" />
        </div>

        <h4 className="text-lg sm:text-xl font-black text-white font-outfit mb-2 tracking-tight">
          {t('Drop your audio files here')}
        </h4>
        <p className="text-xs text-slate-400 max-w-md leading-relaxed">
          {t('Supported: WAV, MP3, FLAC, OGG | Multiple files supported')}
        </p>
      </div>

      {/* Unified Full-Width Online Stream Search & URL Bar */}
      <div className="relative w-full" ref={dropdownRef}>
        <div className="glass-panel p-2 sm:p-2.5 rounded-2xl flex items-center gap-2.5 sm:gap-3 border border-white/10 shadow-xl focus-within:border-indigo-500/50 focus-within:ring-2 focus-within:ring-indigo-500/20 transition-all">
          <div className={cn(
            "p-2.5 rounded-xl transition-colors shrink-0 flex items-center justify-center",
            isUrl(inputVal)
              ? "bg-indigo-500/15 text-indigo-400"
              : "bg-red-500/15 text-red-400"
          )}>
            {isUrl(inputVal) ? <LinkIcon className="w-4 h-4" /> : <Youtube className="w-4 h-4" />}
          </div>

          <input
            type="text"
            value={inputVal}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              if (searchResults.length > 0 && !isUrl(inputVal)) {
                setShowSearchDropdown(true);
              }
            }}
            placeholder={t('Search or paste audio/video link (YouTube, SoundCloud...)')}
            className="w-full bg-transparent text-xs sm:text-sm text-white placeholder-slate-500 outline-none px-1 font-medium"
          />

          {/* Clear Input Button */}
          {inputVal && !isDownloadingUrl && (
            <button
              type="button"
              onClick={handleClearInput}
              className="p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-white/10 transition-colors shrink-0"
              title="Temizle"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Action Button */}
          {isUrl(inputVal) ? (
            <button
              onClick={() => handleUrlDownload()}
              disabled={isDownloadingUrl || !inputVal.trim()}
              className="px-4 sm:px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 disabled:opacity-50 text-xs font-bold text-white transition-all duration-200 shrink-0 flex items-center gap-1.5 active:scale-95 shadow-lg shadow-indigo-500/20"
            >
              {isDownloadingUrl ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>{t('Downloading...')}</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  <span>{t('Download')}</span>
                </>
              )}
            </button>
          ) : (
            <button
              type="button"
              onClick={handleImmediateSearch}
              disabled={isSearching || isDownloadingUrl || !inputVal.trim()}
              className="px-3.5 sm:px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 disabled:opacity-50 text-xs font-bold text-slate-300 hover:text-white transition-all shrink-0 flex items-center gap-2 border border-white/5 active:scale-95"
            >
              {isSearching ? (
                <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
              ) : (
                <Search className="w-3.5 h-3.5" />
              )}
              <span className="hidden sm:inline">Ara</span>
            </button>
          )}
        </div>

        {/* Hidden YouTube Preview Player Container */}
        <div id="yt-hidden-preview-player" className="absolute -left-[9999px] -top-[9999px] w-1 h-1 opacity-0 pointer-events-none" />

        {/* Full-Width Search Dropdown Modal */}
        {showSearchDropdown && searchResults.length > 0 && !isUrl(inputVal) && (
          <div
            onScroll={(e) => {
              const el = e.currentTarget;
              if (el.scrollHeight - el.scrollTop - el.clientHeight < 30) {
                loadMoreResults();
              }
            }}
            className="absolute top-full left-0 right-0 mt-2 bg-slate-900/95 border border-white/15 backdrop-blur-2xl rounded-3xl shadow-2xl p-2.5 z-50 max-h-96 overflow-y-auto space-y-1.5 custom-scrollbar animate-fade-in"
          >
            {/* Search Dropdown Header with Count & Close Button */}
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/10 text-xs text-slate-400">
              <span className="font-bold text-white flex items-center gap-1.5 text-[11px]">
                <Youtube className="w-3.5 h-3.5 text-red-500" />
                <span>YouTube Sonuçları ({searchResults.length})</span>
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  closeAndClearSearch();
                }}
                className="px-2.5 py-1 rounded-lg bg-white/10 hover:bg-rose-500/20 hover:text-rose-300 text-[10px] font-bold text-slate-300 transition-all flex items-center gap-1 cursor-pointer active:scale-95"
                title="Aramayı Kapat ve Çalan Şarkıyı Durdur"
              >
                <X className="w-3 h-3" />
                <span>Kapat</span>
              </button>
            </div>

            {searchResults.map((res, i) => {
              const vidId = extractVideoId(res);
              const isThisPlaying = Boolean(vidId && playingVideoId === vidId);

              return (
                <div
                  key={i}
                  onClick={() => selectSearchResult(res)}
                  className={cn(
                    "p-3 rounded-2xl cursor-pointer transition-all text-left group border",
                    isThisPlaying
                      ? "bg-slate-800/90 border-emerald-500/40 shadow-lg shadow-emerald-500/10 ring-1 ring-emerald-500/20"
                      : "hover:bg-white/[0.08] border-transparent hover:border-white/10"
                  )}
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3.5 min-w-0 flex-1">
                      {/* Thumbnail with Play/Pause Interactive Overlay */}
                      <div
                        onClick={(e) => togglePlayPreview(res, e)}
                        className={cn(
                          "relative w-16 h-10 sm:w-20 sm:h-12 rounded-xl overflow-hidden bg-slate-800 shrink-0 border transition-all shadow-md group/thumb cursor-pointer",
                          isThisPlaying
                            ? "border-emerald-400 ring-2 ring-emerald-400/40 shadow-emerald-500/30"
                            : "border-white/10 group-hover:border-indigo-500/50"
                        )}
                        title={isThisPlaying && isPlayingPreview ? "Duraklat" : "Önizle ve Dinle"}
                      >
                        {res.thumbnail ? (
                          <img
                            src={res.thumbnail}
                            alt={res.title}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                            loading="lazy"
                            onError={(e) => {
                              e.currentTarget.style.display = 'none';
                              const fb = e.currentTarget.parentElement?.querySelector('.yt-fallback') as HTMLElement;
                              if (fb) fb.style.display = 'flex';
                            }}
                          />
                        ) : null}
                        
                        <div className={cn(
                          "yt-fallback absolute inset-0 items-center justify-center bg-red-500/10 text-red-400",
                          res.thumbnail ? "hidden" : "flex"
                        )}>
                          <Youtube className="w-5 h-5" />
                        </div>

                        {/* Play/Pause Hover / Active Overlay */}
                        <div className={cn(
                          "absolute inset-0 flex items-center justify-center transition-all",
                          isThisPlaying
                            ? "bg-black/60 backdrop-blur-[1px] opacity-100"
                            : "bg-black/50 backdrop-blur-[1px] opacity-0 group-hover/thumb:opacity-100"
                        )}>
                          {isThisPlaying ? (
                            isBufferingPreview ? (
                              <Loader2 className="w-5 h-5 text-emerald-400 animate-spin" />
                            ) : isPlayingPreview ? (
                              <div className="w-7 h-7 rounded-full bg-emerald-500 text-black flex items-center justify-center shadow-lg transform active:scale-90 transition-transform">
                                <Pause className="w-3.5 h-3.5 fill-current" />
                              </div>
                            ) : (
                              <div className="w-7 h-7 rounded-full bg-emerald-500 text-black flex items-center justify-center shadow-lg transform active:scale-90 transition-transform">
                                <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
                              </div>
                            )
                          ) : (
                            <div className="w-7 h-7 rounded-full bg-emerald-500/90 hover:bg-emerald-400 text-black flex items-center justify-center shadow-lg transform active:scale-90 transition-transform">
                              <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Song Title & Channel */}
                      <div className="min-w-0 flex-1">
                        <div className={cn(
                          "text-xs font-bold truncate transition-colors",
                          isThisPlaying ? "text-emerald-300" : "text-slate-200 group-hover:text-white"
                        )}>
                          {res.title}
                        </div>
                        {res.channel && (
                          <div className="text-[10px] text-slate-400 truncate mt-0.5 font-medium">
                            {res.channel}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right Duration & Download Badge */}
                    <div className="flex items-center gap-2.5 shrink-0">
                      {res.duration && (
                        <span className="text-[10px] text-slate-400 font-mono bg-black/50 border border-white/5 px-2.5 py-1 rounded-lg">
                          ⏱️ {typeof res.duration === 'number' ? formatTime(res.duration) : res.duration}
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          selectSearchResult(res);
                        }}
                        className="text-[11px] font-bold text-indigo-300 hover:text-white bg-indigo-500/15 hover:bg-indigo-500/30 border border-indigo-500/30 px-3 py-1.5 rounded-xl transition-all flex items-center gap-1.5 shadow-sm active:scale-95"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>İndir</span>
                      </button>
                    </div>
                  </div>

                  {/* Active Song Live Audio Progress Bar */}
                  {isThisPlaying && (
                    <div
                      className="mt-3 pt-2.5 border-t border-white/10 flex items-center gap-3 animate-fade-in"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={(e) => togglePlayPreview(res, e)}
                        className="p-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 transition-colors shrink-0 active:scale-95"
                        title={isPlayingPreview ? "Duraklat" : "Oynat"}
                      >
                        {isBufferingPreview ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : isPlayingPreview ? (
                          <Pause className="w-4 h-4 fill-current" />
                        ) : (
                          <Play className="w-4 h-4 fill-current ml-0.5" />
                        )}
                      </button>

                      <span className="text-[10px] font-mono font-bold text-emerald-400 shrink-0 min-w-[35px]">
                        {formatTime(previewCurrentTime)}
                      </span>

                      {/* Interactive Scrubber Track & Glowing Thumb */}
                      <div
                        onClick={(e) => {
                          const rect = e.currentTarget.getBoundingClientRect();
                          const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                          handleSeekPreview(frac, e);
                        }}
                        className="relative flex-1 py-3 cursor-pointer group/bar flex items-center select-none"
                        title="İleri / Geri Sar"
                      >
                        {/* Background Base Track */}
                        <div className="w-full h-1.5 sm:h-2 bg-slate-950/90 rounded-full overflow-hidden border border-white/10 group-hover/bar:h-2 sm:group-hover/bar:h-2.5 transition-all">
                          {/* Progress Fill */}
                          <div
                            className="h-full bg-gradient-to-r from-emerald-400 via-teal-400 to-indigo-500 rounded-full transition-[width] duration-100"
                            style={{
                              width: `${Math.min(100, Math.max(0, (previewCurrentTime / (previewDuration || 1)) * 100))}%`,
                            }}
                          />
                        </div>

                        {/* Draggable Glowing Handle Circle (Thumb) */}
                        <div
                          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 sm:w-4 sm:h-4 bg-white rounded-full shadow-lg shadow-emerald-500/50 border-2 border-emerald-400 pointer-events-none transform group-hover/bar:scale-125 transition-transform"
                          style={{
                            left: `${Math.min(100, Math.max(0, (previewCurrentTime / (previewDuration || 1)) * 100))}%`,
                          }}
                        />
                      </div>

                      <span className="text-[10px] font-mono text-slate-400 shrink-0 min-w-[35px]">
                        {formatTime(previewDuration)}
                      </span>

                      <button
                        type="button"
                        onClick={(e) => stopPreview(e)}
                        className="p-1.5 rounded-xl text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors shrink-0"
                        title="Önizlemeyi Durdur"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Loading More Indicator at Bottom */}
            {isLoadingMore && (
              <div className="p-3 text-center flex items-center justify-center gap-2 text-indigo-400 text-xs font-semibold">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Daha fazla sonuç yükleniyor...</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Audio Queue List */}
      {queue.length > 0 && (
        <div className="glass-panel rounded-3xl p-6 sm:p-8 space-y-4 border border-white/10 shadow-2xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <FileAudio className="w-4 h-4 text-indigo-400" />
              <h5 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Processing Queue ({queue.length})
              </h5>
            </div>
            <button
              onClick={onClearQueue}
              className="text-xs text-rose-400 hover:text-rose-300 transition-colors font-medium"
            >
              Clear All
            </button>
          </div>

          <div className="space-y-2 max-h-56 overflow-y-auto pr-1 custom-scrollbar">
            {queue.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-950/70 border border-white/5 text-xs hover:border-white/10 transition-all"
              >
                <div className="flex items-center gap-3 truncate">
                  <div className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse shadow-[0_0_8px_rgba(99,102,241,0.8)]" />
                  <span className="font-bold text-white truncate">{item.name}</span>
                  {item.size && (
                    <span className="text-[10px] text-slate-500 font-mono">
                      {formatBytes(item.size)}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => onRemoveFromQueue(item.id)}
                  className="p-1.5 rounded-xl hover:bg-white/10 text-slate-500 hover:text-rose-400 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          {/* AI Separation Trigger Button */}
          <button
            onClick={onStartSeparation}
            disabled={isProcessing || queue.length === 0}
            className={cn(
              'w-full py-4 rounded-2xl text-white font-bold text-sm flex items-center justify-center gap-3 transition-all duration-300 shadow-2xl active:scale-[0.98] disabled:opacity-50 relative overflow-hidden group',
              accentColor === 'indigo' &&
                'bg-gradient-to-r from-indigo-600 via-indigo-500 to-indigo-700 shadow-indigo-500/30',
              accentColor === 'emerald' &&
                'bg-gradient-to-r from-emerald-600 via-emerald-500 to-emerald-700 shadow-emerald-500/30',
              accentColor === 'rose' &&
                'bg-gradient-to-r from-rose-600 via-rose-500 to-rose-700 shadow-rose-500/30',
              accentColor === 'amber' &&
                'bg-gradient-to-r from-amber-600 via-amber-500 to-amber-700 shadow-amber-500/30',
              accentColor === 'violet' &&
                'bg-gradient-to-r from-violet-600 via-violet-500 to-violet-700 shadow-violet-500/30'
            )}
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>{t('Separating Audio Tracks')}...</span>
              </>
            ) : (
              <>
                <Play className="w-5 h-5 fill-white transition-transform group-hover:scale-110" />
                <span className="tracking-wide">
                  {queue.length > 1 ? t('Run Batch Separation') : t('Run AI Separation')}
                </span>
                <Sparkles className="w-4 h-4 opacity-70 animate-pulse" />
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
};
