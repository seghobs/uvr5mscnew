'use client';

import { EditHistory, protectLockedRows, segmentSignature } from '@/lib/edit-history';
import { registerProjectFlusher, projectStorage } from '@/lib/project-storage';

import {StudioSelect} from './StudioSelect';
import {updateLyricInput} from '@/lib/lyric-input';

import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import {KaraokeVideoPreview} from './KaraokeVideoPreview';
import { KaraokeToolPopover } from './KaraokeToolPopover';
import {
  Video,
  X,
  Download,
  Loader2,
  Sparkles,
  Smartphone,
  Monitor,
  CheckCircle2,
  Play,
  Pause,
  Plus,
  Trash2,
  Mic2,
  Music,
  Palette,
  Edit3,
  Database,
  RotateCcw,
  FastForward,
  Repeat,
  Radio,
  Undo2,
  ArrowRight,
  FolderUp,
  FolderDown,
  ChevronDown,
  FileCode,
  Crown,
  ClipboardPaste,
  Zap,
  Check,
  Globe,
  Languages,
  Type,
  Sliders,
  Wand2,
} from 'lucide-react';
import { Language, LyricSegment } from '@/lib/types';
import { getTranslation } from '@/lib/translations';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { preserveWords, reconcileWords, uppercaseLyric, uppercaseLyrics, videoSegments, timingIssues, wordFillWithNeighbors, serializeProject, importProject, enqueueLyricsSave, rowPlaybackRange, repairTiming, TimedWord } from '@/lib/karaoke-timing';
import LyricsReferenceModal from './LyricsReferenceModal';
import { WordPlayer, checkWordInterval } from '@/lib/word-player';
import { AudioPassageEditor } from './AudioPassageEditor';
import {recordLiveRow, clearLiveTimings} from '@/lib/live-sync';
import { preservePassages, bindDetectedWords, bindDetectedSyllables, bindAllRows, passagePool, poolKey, validRange } from '@/lib/audio-passages';

interface KaraokeStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
  instStem: string;
  vocalStem?: string;
  lang: Language;
  onNotify: (type: 'success' | 'error' | 'warning' | 'info', title: string, message?: string, duration?: number) => void;
}

const WHISPER_LANGUAGES = [
  { code: 'auto', name: 'Otomatik Algıla (Auto Detect)', native: 'Auto', flag: '🌐', popular: true },
  { code: 'tr', name: 'Türkçe', native: 'Türkçe', flag: '🇹🇷', popular: true },
  { code: 'en', name: 'İngilizce (English)', native: 'English', flag: '🇬🇧', popular: true },
  { code: 'ko', name: 'Korece (Korean)', native: '한국어', flag: '🇰🇷', popular: true },
  { code: 'ja', name: 'Japonca (Japanese)', native: '日本語', flag: '🇯🇵', popular: true },
  { code: 'es', name: 'İspanyolca (Spanish)', native: 'Español', flag: '🇪🇸', popular: true },
  { code: 'fr', name: 'Fransızca (French)', native: 'Français', flag: '🇫🇷', popular: true },
  { code: 'de', name: 'Almanca (German)', native: 'Deutsch', flag: '🇩🇪', popular: true },
  { code: 'ar', name: 'Arapça (Arabic)', native: 'العربية', flag: '🇸🇦', popular: true },
  { code: 'ru', name: 'Rusça (Russian)', native: 'Русский', flag: '🇷🇺', popular: true },
  { code: 'it', name: 'İtalyanca (Italian)', native: 'Italiano', flag: '🇮🇹', popular: true },
  { code: 'pt', name: 'Portekizce (Portuguese)', native: 'Português', flag: '🇵🇹', popular: true },
  { code: 'zh', name: 'Çince (Chinese)', native: '中文', flag: '🇨🇳', popular: true },
  { code: 'az', name: 'Azerbaycan Türkçesi', native: 'Azərbaycan', flag: '🇦🇿', popular: true },
  { code: 'hi', name: 'Hintçe (Hindi)', native: 'हिन्दी', flag: '🇮🇳', popular: true },
  { code: 'fa', name: 'Farsça (Persian)', native: 'فارسی', flag: '🇮🇷', popular: true },
  { code: 'el', name: 'Yunanca (Greek)', native: 'Ελληνικά', flag: '🇬🇷', popular: false },
  { code: 'nl', name: 'Felemenkçe (Dutch)', native: 'Nederlands', flag: '🇳🇱', popular: false },
  { code: 'sv', name: 'İsveççe (Swedish)', native: 'Svenska', flag: '🇸🇪', popular: false },
  { code: 'pl', name: 'Lehçe (Polish)', native: 'Polski', flag: '🇵🇱', popular: false },
  { code: 'uk', name: 'Ukraynaca (Ukrainian)', native: 'Українська', flag: '🇺🇦', popular: false },
  { code: 'ro', name: 'Romence (Romanian)', native: 'Română', flag: '🇷🇴', popular: false },
  { code: 'hu', name: 'Macarca (Hungarian)', native: 'Magyar', flag: '🇭🇺', popular: false },
  { code: 'cs', name: 'Çekçe (Czech)', native: 'Čeština', flag: '🇨🇿', popular: false },
  { code: 'he', name: 'İbranice (Hebrew)', native: 'עברית', flag: '🇮🇱', popular: false },
  { code: 'id', name: 'Endonezce (Indonesian)', native: 'Bahasa Indonesia', flag: '🇮🇩', popular: false },
  { code: 'th', name: 'Tayca (Thai)', native: 'ไทย', flag: '🇹🇭', popular: false },
  { code: 'vi', name: 'Vietnamca (Vietnamese)', native: 'Tiếng Việt', flag: '🇻🇳', popular: false },
  { code: 'bg', name: 'Bulgarca (Bulgarian)', native: 'Български', flag: '🇧🇬', popular: false },
  { code: 'hr', name: 'Hırvatça (Croatian)', native: 'Hrvatski', flag: '🇭🇷', popular: false },
  { code: 'sr', name: 'Sırpça (Serbian)', native: 'Српски', flag: '🇷🇸', popular: false },
  { code: 'sk', name: 'Slovakça (Slovak)', native: 'Slovenčina', flag: '🇸🇰', popular: false },
  { code: 'da', name: 'Danca (Danish)', native: 'Dansk', flag: '🇩🇰', popular: false },
  { code: 'fi', name: 'Fince (Finnish)', native: 'Suomi', flag: '🇫🇮', popular: false },
  { code: 'no', name: 'Norveççe (Norwegian)', native: 'Norsk', flag: '🇳🇴', popular: false },
  { code: 'ca', name: 'Katalanca (Catalan)', native: 'Català', flag: '🇪🇸', popular: false },
  { code: 'ur', name: 'Urduca (Urdu)', native: 'اردو', flag: '🇵🇰', popular: false },
  { code: 'ms', name: 'Malayca (Malay)', native: 'Bahasa Melayu', flag: '🇲🇾', popular: false },
  { code: 'kk', name: 'Kazakça (Kazakh)', native: 'Қазақша', flag: '🇰🇿', popular: false },
  { code: 'uz', name: 'Özbekçe (Uzbek)', native: 'Oʻzbekcha', flag: '🇺🇿', popular: false },
];

// Legacy call sites retain their signature, but measured times must NEVER be stretched.
export const fitWordsToSegmentRange = (words: TimedWord[], _start: number, _end: number, _text: string): TimedWord[] => preserveWords(words);

export const KaraokeStudioModal: React.FC<KaraokeStudioModalProps> = ({
  isOpen,
  onClose,
  instStem,
  vocalStem,
  lang,
  onNotify,
}) => {
  const t = (key: string) => getTranslation(lang, key);

  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const [segments, setRawSegments] = useState<LyricSegment[]>([]);
  const committedSegments=useRef<LyricSegment[]>([]);
  const rowTextBaseline=useRef<Record<string,TimedWord[]>>({});
  type Snapshot={segments:LyricSegment[];pools:Record<string,string>};
  const history=useRef(new EditHistory<Snapshot>({segments:[],pools:{}}));
  const historyKey='uvr-history:'+(vocalStem||instStem);
  const readPools=()=>{const result:Record<string,string>={};const prefixes=['uvr-passages-v2:','uvr-passages-v3:'].map(p=>p+(vocalStem||instStem)+':');for(const key of projectStorage.keys()){if(prefixes.some(p=>key.startsWith(p))&&projectStorage.getItem(key)!==null)result[key]=projectStorage.getItem(key)!;}return result;};
  const persistHistory=()=>projectStorage.setItem(historyKey,JSON.stringify(history.current.serialize()));
  const loadSegments=(rows:LyricSegment[])=>{
    const next=repairTiming(rows).map(row=>({...row,id:row.id||crypto.randomUUID()}));
    next.forEach((row,index)=>{const old=projectStorage.getItem(poolKey(vocalStem||instStem,index,row.start));const key=poolKey(vocalStem||instStem,index,row.start,row.id);if(old&&!projectStorage.getItem(key))projectStorage.setItem(key,old);});
    const snapshot={segments:next,pools:readPools()};
    history.current=new EditHistory(snapshot);
    try{const saved=JSON.parse(projectStorage.getItem(historyKey)||'null');if(saved&&segmentSignature(saved.current.segments)===segmentSignature(next))history.current.restore(saved);}catch{}
    committedSegments.current=next;segmentsRef.current=next;setRawSegments(next);
  };
  const commitSegments=(next:LyricSegment[],allowLocked=false)=>{
    const previous=committedSegments.current;
    const protectedRows=allowLocked?next:protectLockedRows(previous,next);
    const repaired=repairTiming(protectedRows).map(row=>({...row,id:row.id||crypto.randomUUID()}));
    if(JSON.stringify(previous)===JSON.stringify(repaired))return;
    committedSegments.current=repaired;segmentsRef.current=repaired;
    if(allowLocked)history.current.breakGroup();
    history.current.push({segments:repaired,pools:readPools()});
    if(allowLocked)history.current.breakGroup();
    persistHistory();setRawSegments(repaired);triggerAutoSave(repaired);
  };
  const setSegments: React.Dispatch<React.SetStateAction<LyricSegment[]>> = update => {
    const previous=committedSegments.current;
    commitSegments(typeof update==='function'?update(previous):update);
  };
  const restoreEdit=(direction:'undo'|'redo')=>{
    if(isLiveSyncMode){onNotify('warning','Önce canlı senkronu bitir');return;}
    const snapshot=history.current[direction]();if(!snapshot)return;
    for(const key of Object.keys(readPools()))if(!(key in snapshot.pools))projectStorage.removeItem(key);
    for(const [key,value] of Object.entries(snapshot.pools))projectStorage.setItem(key,value);
    committedSegments.current=snapshot.segments;segmentsRef.current=snapshot.segments;setRawSegments(snapshot.segments);persistHistory();triggerAutoSave(snapshot.segments,true);
  };
  const toggleRowLock=(index:number)=>commitSegments(committedSegments.current.map((row,i)=>i===index?{...row,locked:!row.locked}:row),true);
  const [loadingLyrics, setLoadingLyrics] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [renderStatusMsg, setRenderStatusMsg] = useState('FFmpeg 1080p Render Ediliyor...');
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [videoFilename, setVideoFilename] = useState('karaoke_video_1080p.mp4');

  // SQLite Persistence State
  const [isSavingDb, setIsSavingDb] = useState(false);
  const [lastSavedTime, setLastSavedTime] = useState<string | null>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Import / Export & Whisper Model State
  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const importFileInputRef = useRef<HTMLInputElement>(null);

  const [whisperModel, setWhisperModel] = useState<'large-v3' | 'large-v3-turbo'>('large-v3');
  const [showWhisperMenu, setShowWhisperMenu] = useState(false);
  const whisperMenuRef = useRef<HTMLDivElement>(null);

  // Whisper Language Selector State (Supports 99+ Languages & Auto Detect)
  const [selectedLyricsLang, setSelectedLyricsLang] = useState<string>('auto');
  const [showLangMenu, setShowLangMenu] = useState(false);
  const [langSearchQuery, setLangSearchQuery] = useState('');
  const langMenuRef = useRef<HTMLDivElement>(null);

  // Paste & Auto-Align Lyrics Modal State
  const [showPasteModal, setShowPasteModal] = useState(false);
  const [pastedLyricsText, setPastedLyricsText] = useState('');
  const [showReferenceModal, setShowReferenceModal] = useState(false);
  const [isAligningPasted, setIsAligningPasted] = useState(false);

  // Close dropdowns on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if ((event.target as Element)?.closest?.('[data-karaoke-tool-popover]')) return;
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target as Node)) {
        setShowExportMenu(false);
      }
      if (whisperMenuRef.current && !whisperMenuRef.current.contains(event.target as Node)) {
        setShowWhisperMenu(false);
      }
      if (langMenuRef.current && !langMenuRef.current.contains(event.target as Node)) {
        setShowLangMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Video Customization & Header Banner
  const [aspectRatio, setAspectRatio] = useState<'16:9' | '9:16'>('16:9');
  const [theme, setTheme] = useState<'gold' | 'neon' | 'cyberpunk' | 'emerald'>('gold');
  const [headerPrefix, setHeaderPrefix] = useState('KARAOKE STUDIO');
  const [showHeader, setShowHeader] = useState(true);
  const [title, setTitle] = useState(() => {
    const clean = instStem
      .replace(/\.[^/.]+$/, '')
      .replace(/^(Ensemble|BS-Roformer|MDX|Demucs|VR|UVR)_/i, '')
      .replace(/_(Instrumental|Vocals|other|vocals|inst|drums|bass)/gi, '')
      .replace(/_\d{6,}/g, '')
      .replace(/_/g, ' ')
      .trim();
    return clean || 'Karaoke Track';
  });
  const [artist, setArtist] = useState('UVR5 AI Studio');
  const [activeTab, setActiveTab] = useState<'verify' | 'lyrics' | 'video'>('verify');
  const [showAdvancedTools, setShowAdvancedTools] = useState(false);
  const [selectedWordIndex, setSelectedWordIndex] = useState(0);

  // Precision Audio Player State
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const progressBarRef = useRef<HTMLDivElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [activeAudioSource, setActiveAudioSource] = useState<'vocal' | 'inst'>(vocalStem ? 'vocal' : 'inst');
  const [loopLineIndex, setLoopLineIndex] = useState<number | null>(null);
  const [activePlayingIndex, setActivePlayingIndex] = useState<number | null>(null);
  const [activePlayingWord, setActivePlayingWord] = useState<{ segIdx: number; wordIdx: number } | null>(null);
  const [hoverTime, setHoverTime] = useState<number | null>(null);

  const wordPlayerRef = useRef<WordPlayer | null>(null);
  const wordRequestRef = useRef(0);
  const editedPlaybackStartRef = useRef<number | null>(null);
  const segmentsRef = useRef(segments);
  const loopLineRef = useRef(loopLineIndex);
  segmentsRef.current = segments;
  loopLineRef.current = loopLineIndex;
  const stopWordPreview = () => {
    wordRequestRef.current++;
    const wasPlaying = wordPlayerRef.current?.playing;
    const position = wordPlayerRef.current?.currentTime;
    wordPlayerRef.current?.stop();
    if (wasPlaying) {
      if (audioRef.current && position !== undefined) audioRef.current.currentTime = position;
      setIsPlaying(false);
    }
    setActivePlayingWord(null);
  };

  // Auto-stop audio refs for precision word/line previews
  const wordPreviewEndRef = useRef<number | null>(null);
  const linePreviewEndRef = useRef<number | null>(null);

  // Smule Spacebar Live Synchronization State
  const [isLiveSyncMode, setIsLiveSyncMode] = useState(false);
  const [liveGesture,setLiveGesture]=useState<'tap'|'hold'>('tap');
  const liveCaptureRef=useRef<{index:number;start:number}|null>(null);
  const [bulkBindingStatus,setBulkBindingStatus]=useState('');
  const bulkBindingAbort=useRef<AbortController|null>(null);
  useEffect(()=>()=>{bulkBindingAbort.current?.abort();},[isOpen,vocalStem,instStem]);
  const [bulkBindingProblems,setBulkBindingProblems]=useState<string[]>([]);
  const liveSpaceHandledRef = useRef(false);
  const liveSyncFinishedRef = useRef(false);
  const [liveSyncIndex, setLiveSyncIndex] = useState<number>(0);
  const [isSpacePressed, setIsSpacePressed] = useState(false);
  const [spacePressStartTime, setSpacePressStartTime] = useState<number | null>(null);
  const [passageRow, setPassageRow] = useState<{index:number; original:LyricSegment} | null>(null);
  const [expandedWordRow, setExpandedWordRow] = useState<number | null>(null);
  const rowRefs = useRef<{ [key: number]: HTMLDivElement | null }>({});

  // Stop audio on close
  useEffect(() => {
    if (!isOpen && audioRef.current) {
      liveSyncFinishedRef.current=false;
      editedPlaybackStartRef.current = null;
      stopWordPreview();
      audioRef.current.pause();
      setIsPlaying(false);
      setActivePlayingIndex(null);
      setActivePlayingWord(null);
      wordPreviewEndRef.current = null;
      linePreviewEndRef.current = null;
      setIsLiveSyncMode(false);
    }
  }, [isOpen]);

  // Audio Engine Lifecycle
  useEffect(() => {
    if (!isOpen) return;
    const audioFile = activeAudioSource === 'vocal' && vocalStem ? vocalStem : instStem;
    if (!audioFile) return;

    if (!audioRef.current) {
      audioRef.current = new Audio();
    }
    const audio = audioRef.current;
    const wasPlaying = isPlaying;
    const savedPos = audio.currentTime || 0;

    stopWordPreview();
    audio.src = `/output/${encodeURIComponent(audioFile)}`;
    audio.load();

    const handleLoadedMetadata = () => {
      setDuration(audio.duration || 0);
      const restorePosition = editedPlaybackStartRef.current ?? savedPos;
      if (restorePosition >= 0 && restorePosition < audio.duration) {
        audio.currentTime = restorePosition;
      }
      if (wasPlaying) {
        audio.play().catch(() => {});
      }
    };

    const handleTimeUpdate = () => {
      if (!wordPlayerRef.current?.playing) setCurrentTime(audio.currentTime);

      // Handle Word Preview Auto-Stop
      if (wordPreviewEndRef.current !== null && audio.currentTime >= wordPreviewEndRef.current) {
        audio.pause();
        wordPreviewEndRef.current = null;
        setActivePlayingWord(null);
      }

      // Handle Line Preview Auto-Stop (when not looping)
      if (linePreviewEndRef.current !== null && loopLineRef.current === null && audio.currentTime >= linePreviewEndRef.current) {
        audio.pause();
        linePreviewEndRef.current = null;
        setActivePlayingIndex(null);
      }

      // Handle Line Loop Mode
      if (loopLineRef.current !== null && segmentsRef.current[loopLineRef.current]) {
        const targetSeg = rowPlaybackRange(segmentsRef.current[loopLineRef.current]);
        if (audio.currentTime >= targetSeg.end) {
          audio.currentTime = targetSeg.start;
        }
      }
    };

    const handleEnded = () => {
      setIsPlaying(false);
      setActivePlayingIndex(null);
      setActivePlayingWord(null);
      wordPreviewEndRef.current = null;
      linePreviewEndRef.current = null;
      setIsSpacePressed(false);
    };

    const handlePlayEvent = () => setIsPlaying(true);
    const handlePauseEvent = () => {
      if (wordPlayerRef.current?.playing) return;
      setIsPlaying(false);
      setIsSpacePressed(false);
      setActivePlayingWord(null);
      wordPreviewEndRef.current = null;
      linePreviewEndRef.current = null;
    };

    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('play', handlePlayEvent);
    audio.addEventListener('pause', handlePauseEvent);

    return () => {
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('play', handlePlayEvent);
      audio.removeEventListener('pause', handlePauseEvent);
    };
  }, [isOpen, activeAudioSource, vocalStem, instStem]);

  useEffect(() => {
    if (!isOpen) return;
    let frame = 0;
    const tick = () => {
      const precise = wordPlayerRef.current;
      if (precise?.playing) setCurrentTime(precise.currentTime);
      else if (audioRef.current && !audioRef.current.paused) setCurrentTime(audioRef.current.currentTime);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [isOpen]);

  useEffect(() => () => {
    audioRef.current?.pause();
    wordPlayerRef.current?.dispose();
  }, []);

  useEffect(() => {
    if (!isOpen || !(vocalStem || instStem)) return;
    wordPlayerRef.current ??= new WordPlayer();
    void wordPlayerRef.current.prepare(`/output/${encodeURIComponent(vocalStem || instStem)}`).catch(() => {});
  }, [isOpen, vocalStem, instStem]);

  // Load lyrics on open
  useEffect(() => {
    if (isOpen) {
      setVideoUrl(null);
      const sourceForLyrics = vocalStem || instStem;
      if (sourceForLyrics) {
        void fetchInitialLyrics(sourceForLyrics, false).catch(() => {});
      }
    }
  }, [isOpen, instStem, vocalStem]);

  // Use a ref for the gesture: React rerenders must not change its start/index.
  const finishLiveRow=(end:number)=>{
    const capture=liveCaptureRef.current;
    if(!capture||!segmentsRef.current[capture.index])return;
    if(end-capture.start<0.08){
      liveCaptureRef.current=null;setIsSpacePressed(false);
      onNotify('warning','Satır kaydedilmedi','Çok kısa basış algılandı. Basılı tut modunda söz boyunca tuşu tutun.');return;
    }
    const original=segmentsRef.current[capture.index];
    const updated=recordLiveRow(original,capture.start,end);
    const next=segmentsRef.current.map((s,i)=>i===capture.index?updated:s);
    if(updated!==original){
      preservePassages(vocalStem||instStem,capture.index,original);
      segmentsRef.current=next;setSegments(next);triggerAutoSave(next);
    }else{
      onNotify('info','Bağlı satır korundu','Bu satırın ses bağlantıları ve süreleri değiştirilmeden sonraki satıra geçildi.');
    }
    const index=capture.index+1;
    setIsSpacePressed(false);setSpacePressStartTime(null);
    if(index<next.length){
      setLiveSyncIndex(index);
      liveCaptureRef.current=liveGesture==='tap'?{index,start:end}:null;
      rowRefs.current[index]?.scrollIntoView({behavior:'smooth',block:'center'});
    }else{
      liveSyncFinishedRef.current=true;
      setLiveSyncIndex(capture.index);
      liveCaptureRef.current=null;setIsLiveSyncMode(false);audioRef.current?.pause();
      stopWordPreview();wordPreviewEndRef.current=null;linePreviewEndRef.current=null;
      loopLineRef.current=null;setLoopLineIndex(null);editedPlaybackStartRef.current=null;
      onNotify('success','Canlı senkron tamamlandı','Son satırda kalındı. Bağlı kelimeler korundu; yeniden başlatmak için canlı senkron düğmesini kullan.');
    }
  };
  useEffect(()=>{
    if(!isOpen||loadingLyrics||(!isLiveSyncMode&&!liveSyncFinishedRef.current&&(activeTab!=='lyrics'||passageRow||showReferenceModal||showPasteModal)))return;
    const typing=()=>{const el=document.activeElement as HTMLElement|null;return !!el&&(el.isContentEditable||['INPUT','TEXTAREA','SELECT'].includes(el.tagName));};
    const down=(e:KeyboardEvent)=>{
      if((e.target as Element|null)?.closest?.('[data-studio-select]'))return;
      if(isLiveSyncMode&&(e.code==='Enter'||e.code==='NumpadEnter')){
        e.preventDefault();e.stopImmediatePropagation();
        liveCaptureRef.current=null;
        setIsSpacePressed(false);setSpacePressStartTime(null);
        setIsLiveSyncMode(false);
        audioRef.current?.pause();stopWordPreview();
        wordPreviewEndRef.current=null;linePreviewEndRef.current=null;
        loopLineRef.current=null;setLoopLineIndex(null);editedPlaybackStartRef.current=null;
        return;
      }
      if(e.code==='Space'){
        if(liveSyncFinishedRef.current&&!isLiveSyncMode&&!typing()){
          e.preventDefault();e.stopImmediatePropagation();liveSpaceHandledRef.current=true;return;
        }
        if(!isLiveSyncMode&&typing())return;
        if(isLiveSyncMode){liveSpaceHandledRef.current=true;e.stopImmediatePropagation();}
        e.preventDefault();if(e.repeat)return;
        if(!isLiveSyncMode){toggleMasterPlay();return;}
        const audio=audioRef.current;if(!audio)return;
        const now=audio.currentTime;
        const wasPaused=audio.paused;
        if(liveGesture==='tap'){
          if(!liveCaptureRef.current)liveCaptureRef.current={index:liveSyncIndex,start:now};
          else if(now-liveCaptureRef.current.start>=0.08)finishLiveRow(now);
        }else if(!liveCaptureRef.current){
          liveCaptureRef.current={index:liveSyncIndex,start:now};setIsSpacePressed(true);setSpacePressStartTime(now);
        }
        // Resume after processing this press; do not swallow the first boundary.
        // A completed final row clears the capture and must remain paused.
        if(wasPaused&&liveCaptureRef.current)audio.play().catch(()=>{});
      }else if(isLiveSyncMode&&!typing()){
        if(e.code==='Escape'){liveCaptureRef.current=null;setIsSpacePressed(false);setIsLiveSyncMode(false);}
        if(e.code==='Backspace'){e.preventDefault();handleLiveSyncPrev();}
        if(e.code==='ArrowRight'||e.code==='Tab'){e.preventDefault();handleLiveSyncNext();}
      }
    };
    const up=(e:KeyboardEvent)=>{
      if(e.code!=='Space'||(!isLiveSyncMode&&!liveSpaceHandledRef.current))return;
      e.preventDefault();
      e.stopImmediatePropagation();liveSpaceHandledRef.current=false;
      if(isLiveSyncMode&&liveGesture==='hold'&&liveCaptureRef.current&&audioRef.current&&!audioRef.current.paused)finishLiveRow(audioRef.current.currentTime);
    };
    const blur=()=>{if(liveGesture==='hold')liveCaptureRef.current=null;liveSpaceHandledRef.current=false;setIsSpacePressed(false);};
    window.addEventListener('keydown',down,true);window.addEventListener('keyup',up,true);window.addEventListener('blur',blur);
    return ()=>{window.removeEventListener('keydown',down,true);window.removeEventListener('keyup',up,true);window.removeEventListener('blur',blur);};
  },[isOpen,activeTab,isLiveSyncMode,liveSyncIndex,liveGesture,loadingLyrics,isPlaying,passageRow,showReferenceModal,showPasteModal]);

  const handleLiveSyncPrev = () => {
    liveCaptureRef.current=null;setIsSpacePressed(false);
    if (liveSyncIndex > 0) {
      const prevIdx = liveSyncIndex - 1;
      setLiveSyncIndex(prevIdx);
      if (segments[prevIdx] && audioRef.current) {
        // Rewind slightly before the previous line
        const jumpTime = Math.max(0, segments[prevIdx].start - 1.0);
        seekTo(jumpTime);
        liveCaptureRef.current=liveGesture==='tap'?{index:prevIdx,start:jumpTime}:null;
      }
      rowRefs.current[prevIdx]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const handleLiveSyncNext = () => {
    liveCaptureRef.current=null;setIsSpacePressed(false);
    if (liveSyncIndex < segments.length - 1) {
      const nextIdx = liveSyncIndex + 1;
      setLiveSyncIndex(nextIdx);
      liveCaptureRef.current=liveGesture==='tap'&&audioRef.current?{index:nextIdx,start:audioRef.current.currentTime}:null;
      rowRefs.current[nextIdx]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const startLiveSyncMode = (targetIndex = 0) => {
    liveSyncFinishedRef.current=false;
    setIsLiveSyncMode(true);
    setLiveSyncIndex(targetIndex);
    setIsSpacePressed(false);

    stopWordPreview();wordPreviewEndRef.current=null;linePreviewEndRef.current=null;
    loopLineRef.current=null;setLoopLineIndex(null);editedPlaybackStartRef.current=null;
    const audio=audioRef.current;
    liveCaptureRef.current=liveGesture==='tap'&&audio?{index:targetIndex,start:audio.currentTime}:null;
    if(audio?.paused)audio.play().catch(()=>{});

    rowRefs.current[targetIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    onNotify('info', 'Smule Canlı Senkron Modu Aktif 🎙️', liveGesture==='tap'?'Mevcut konum başlangıç alındı. Satır bitince Space’e bir kez basın.':'Söz başlayınca Space’i basılı tutun, bitince bırakın.');
  };

  const pendingSaveRef = useRef<{ file: string; segments: LyricSegment[]; language: string } | null>(null);
  const bindEveryRow = async () => {
    if(bulkBindingAbort.current)return; const controller=new AbortController();bulkBindingAbort.current=controller;
    setBulkBindingStatus('Hazırlanıyor…');
    try {
    const current=segmentsRef.current;
    const pools=current.map((row,index)=>{
      try {
        const stored=JSON.parse(projectStorage.getItem(poolKey(vocalStem||instStem,index,row.start,row.id))||projectStorage.getItem(poolKey(vocalStem||instStem,index,row.start))||'null');
        if(Array.isArray(stored))return stored.filter(p=>p&&typeof p.id==='string'&&typeof p.label==='string'&&validRange(p.start,p.end));
      }catch {}
      return passagePool(row);
    });
    const result=bindAllRows(current,pools);
    const issues:string[]=[];
    for(let index=0;index<current.length;index++){
      const row=current[index];
      if(result.segments[index]!==row)continue;
      if(/^\s*(solo|enstr[üu]mantal|instrumental)[.\s…!]*$/i.test(row.text))continue;
      setBulkBindingStatus(`Sesten bağlanıyor: ${index+1}/${current.length}`);
      try {
        if(!validRange(row.start,row.end)||row.end-row.start>20)throw Error('Kelime analizi için 20 saniyeyi aşmayan geçerli bir satır süresi gerekli.');
        const response=await fetch('/api/lyrics/syllables',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file_name:vocalStem||instStem,segment:row}),signal:controller.signal});
        const data=await response.json();
        if(response.status===409)throw Error('SUNUCU_MEŞGUL: Başka bir ses analizi çalışıyor. Tamamlandıktan sonra toplu bağlamayı tekrar başlatın.');
        if(!response.ok)throw Error(data.detail||'Ses analizi tamamlanamadı.');
        const updated=Array.isArray(data.word_times)?bindDetectedWords(row,data.word_times):bindDetectedSyllables(row,data.passages);
        const missing=(updated.words||[]).filter(w=>!validRange(w.start,w.end));
        if(missing.length===(updated.words||[]).length)throw Error('Bu satırda güvenilir kelime sınırı bulunamadı. Satır başlangıç/bitişini kontrol edin.');
        result.segments[index]=updated;result.count++;
        if(missing.length)issues.push(`Satır ${index+1}: Bulunan kelimeler bağlandı; kontrol bekleyen: ${missing.map(w=>w.word).join(', ')}`);
      }catch(error){if(controller.signal.aborted||(error as Error).message.startsWith('SUNUCU_MEŞGUL'))throw error;issues.push(`Satır ${index+1}: ${(error as Error).message}`);}
    }
    if(controller.signal.aborted)return;
    if(JSON.stringify(segmentsRef.current)!==JSON.stringify(current))throw Error('Analiz sırasında sözler değişti. Düzenlemelerin korundu; toplu bağlamayı tekrar başlat.');
    result.problems=issues;
    setBulkBindingProblems(issues);
    if(result.count){
      audioRef.current?.pause();stopWordPreview();liveCaptureRef.current=null;setIsLiveSyncMode(false);
      segmentsRef.current=result.segments;setSegments(result.segments);triggerAutoSave(result.segments);
    }
    onNotify(result.problems.length?'warning':'success','Tüm satırlarda ses bağlama',`${result.count} satır bağlandı. ${result.problems.length} satır için kontrol gerekiyor. Sözler korundu.`);
    }catch(error){if(!controller.signal.aborted)onNotify('warning','Toplu bağlama',(error as Error).message);}finally{bulkBindingAbort.current=null;setBulkBindingStatus('');}
  };
  const resumeLiveSyncFromRow = (index: number) => {
    const row = segmentsRef.current[index];
    if (!row || !audioRef.current) return;
    const range = rowPlaybackRange(row);
    const start = Number.isFinite(range.start) && range.start >= 0 && range.end > range.start
      ? range.start : audioRef.current.currentTime;
    setActiveTab('lyrics'); setShowAdvancedTools(false);
    seekTo(start);
    startLiveSyncMode(index);
  };
  const undoAllLiveSync = () => {
    liveSyncFinishedRef.current=false;
    liveCaptureRef.current = null;
    setIsLiveSyncMode(false); setIsSpacePressed(false); setSpacePressStartTime(null);
    audioRef.current?.pause(); stopWordPreview();
    wordPreviewEndRef.current = null; linePreviewEndRef.current = null;
    loopLineRef.current = null; setLoopLineIndex(null); editedPlaybackStartRef.current = null;
    const restored = clearLiveTimings(segmentsRef.current);
    segmentsRef.current = restored; setSegments(restored); triggerAutoSave(restored);
    setLiveSyncIndex(0); seekTo(0);
    onNotify('success', 'Zamanlamalar temizlendi', 'Sözler korundu. Tüm satır ve kelimeler yeniden zamanlanmayı bekliyor.');
  };
  const saveToDatabase = async (segmentsToSave: LyricSegment[], notifyUser = false, sourceFile = vocalStem || instStem, language = selectedLyricsLang) => {
    if (!sourceFile) return;
    const snapshot = repairTiming(segmentsToSave);
    setIsSavingDb(true);
    try {
      await enqueueLyricsSave(() => api.saveLyrics(sourceFile, snapshot, language));
      const draftKey='uvr-lyrics-draft:'+sourceFile;
      try{const draft=JSON.parse(projectStorage.getItem(draftKey)||'null');if(draft&&JSON.stringify(draft.segments)===JSON.stringify(snapshot))projectStorage.removeItem(draftKey);}catch{}
      setLastSavedTime(new Date().toLocaleTimeString());
      if (notifyUser) onNotify('success', 'Kaydedildi', 'Kelime zamanları değiştirilmeden kaydedildi.');
    } catch (err) {
      onNotify('warning', 'Kaydedilemedi', 'Son düzenleme kaydedilemedi. Yeniden kaydetmeyi deneyin.');
      throw err;
    } finally { setIsSavingDb(false); }
  };

  const flushPendingSave = () => {
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = null;
    const pending = pendingSaveRef.current;
    pendingSaveRef.current = null;
    if (pending) void saveToDatabase(pending.segments, false, pending.file, pending.language).catch(() => {});
  };

  const triggerAutoSave = (newSegments: LyricSegment[], immediate = false) => {
    newSegments=protectLockedRows(committedSegments.current,newSegments);
    projectStorage.setItem('uvr-lyrics-draft:'+(vocalStem||instStem),JSON.stringify({segments:newSegments,language:selectedLyricsLang}));
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    pendingSaveRef.current = { file: vocalStem || instStem, segments: structuredClone(newSegments), language: selectedLyricsLang };
    // Keep side effects outside React's state updater; the snapshot is the NEW value.
    saveTimeoutRef.current = setTimeout(flushPendingSave, immediate ? 0 : 350);
  };

  useEffect(() => {
    return () => flushPendingSave();
  }, [isOpen, vocalStem, instStem]);

  useEffect(()=>{if(!isOpen)return;return registerProjectFlusher(async()=>{flushPendingSave();await enqueueLyricsSave(()=>Promise.resolve());if(committedSegments.current.length)await saveToDatabase(committedSegments.current,false);});},[vocalStem,instStem,isOpen]);
  useEffect(()=>{
    if(!isOpen)return;
    const handleHistoryKey=(event:KeyboardEvent)=>{
      if(!(event.ctrlKey||event.metaKey)||passageRow!==null)return;
      if((event.target as HTMLElement)?.closest?.('input,textarea,[contenteditable="true"]'))return;
      const key=event.key.toLowerCase();
      if(key==='z'||key==='y'){event.preventDefault();event.stopPropagation();restoreEdit(key==='y'||event.shiftKey?'redo':'undo');}
    };
    window.addEventListener('keydown',handleHistoryKey,true);return()=>window.removeEventListener('keydown',handleHistoryKey,true);
  },[isOpen,isLiveSyncMode,passageRow]);

  const lyricsRequestRef = useRef(0);
  useEffect(() => () => { lyricsRequestRef.current++; }, [isOpen, vocalStem, instStem]);

  const fetchInitialLyrics = async (
    sourceFile: string,
    force = false,
    targetModel = whisperModel,
    rawLyrics?: string,
    targetLang = selectedLyricsLang
  ) => {
    const requestId = ++lyricsRequestRef.current;
    setLoadingLyrics(true);
    stopWordPreview();
    audioRef.current?.pause();
    flushPendingSave();
    await enqueueLyricsSave(() => Promise.resolve());
    try {
      let pending:{segments:LyricSegment[]}|null=null;
      if(!force){try{pending=JSON.parse(projectStorage.getItem('uvr-lyrics-draft:'+sourceFile)||'null');}catch{}}
      const res = pending?.segments?.length
        ? {status:'success',cached:true,segments:pending.segments} as Awaited<ReturnType<typeof api.transcribeLyrics>>
        : await api.transcribeLyrics(sourceFile, targetLang, force, targetModel, rawLyrics);
      if(pending?.segments?.length)onNotify('info','Bekleyen düzenlemeler geri yüklendi');
      if (requestId !== lyricsRequestRef.current) return;
      if (res.segments && res.segments.length > 0) {
        const syncedSegments = uppercaseLyrics(res.segments).map(seg => ({...seg, words:reconcileWords(seg.words || [],seg.text,seg.start)}));
        loadSegments(syncedSegments);
        if (!res.cached && !rawLyrics) setShowReferenceModal(true);
        if (JSON.stringify(committedSegments.current) !== JSON.stringify(res.segments)||projectStorage.getItem('uvr-lyrics-draft:'+sourceFile)) triggerAutoSave(committedSegments.current, false);
        if (res.cached) {
          const savedAt = res.updated_at
            ? new Date(res.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : 'Kayıtlı';
          setLastSavedTime(savedAt);
          onNotify(
            'success',
            'Veritabanından Yüklendi',
            `${res.segments.length} satır kayıtlı şarkı sözü SQLite veritabanından anında yüklendi.`
          );
        } else {
          setLastSavedTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
          const modelTitle = targetModel === 'large-v3' ? 'Whisper Large-V3 (Full HQ - 32 Katman)' : 'Whisper Large-V3-Turbo (Hızlı)';
          const activeL = WHISPER_LANGUAGES.find((l) => l.code === (targetLang || 'auto')) || { name: targetLang, flag: '🌐' };
          onNotify(
            'success',
            'Sözler Çıkarıldı & Kaydedildi!',
            `${res.segments.length} satır şarkı sözü [${activeL.flag} ${activeL.name}] diliyle ${modelTitle} tarafından başarıyla çıkarıldı.`
          );
        }
      } else {
        loadSegments([]);
      }
    } catch (err: any) {
      if (requestId === lyricsRequestRef.current) onNotify('warning', 'Hizalama tamamlanamadı', err.message || 'Mevcut sözler korundu.');
      throw err;
    } finally {
      if (requestId === lyricsRequestRef.current) setLoadingLyrics(false);
    }
  };

  const handleSegmentChange = (index: number, field: keyof LyricSegment, val: string | number) => {
    if (field === 'text') {
      preservePassages(vocalStem || instStem, index, segments[index]);
      val = uppercaseLyric(String(val));
    }
    setSegments((prev) => {
      const next = [...prev];
      let currentSeg = { ...next[index], [field]: val };
      const s = Number(currentSeg.start) || 0;
      const e = Number(currentSeg.end) || (s + 2.0);
      currentSeg.words = field === 'text' ? reconcileWords(rowTextBaseline.current[currentSeg.id||String(index)] || currentSeg.words || [], currentSeg.text || '', s) : fitWordsToSegmentRange(
        currentSeg.words || [],
        s,
        Math.max(s + 0.1, e),
        currentSeg.text || ''
      );
      next[index] = currentSeg;
      triggerAutoSave(next, false);
      return next;
    });
  };

  // Helper to ensure word-level timestamps exist for a segment
  const getSegmentWords = (seg: LyricSegment): TimedWord[] => {
    const rawWords = (seg.text || '').trim().split(/\s+/).filter(Boolean);
    if (rawWords.length === 0) return [];
    if (seg.words && seg.words.length === rawWords.length) {
      return seg.words;
    }
    return fitWordsToSegmentRange(seg.words || [], seg.start, seg.end, seg.text);
  };

  const handleWordTimeChange = (segIdx: number, wordIdx: number, field: 'start' | 'end', val: number) => {
    const word = getSegmentWords(segments[segIdx])[wordIdx];
    if (!word || !Number.isFinite(val)) return;
    // Discard any already scheduled clip before changing its boundaries.
    stopWordPreview();
    audioRef.current?.pause();
    wordPreviewEndRef.current = null;
    linePreviewEndRef.current = null;
    setActivePlayingIndex(null);
    setIsPlaying(false);
    const start = field === 'start' ? Math.max(0, Number(val.toFixed(3)))
      : val < word.start ? Math.max(0, Number((val - 0.05).toFixed(3))) : word.start;
    editedPlaybackStartRef.current = start;
    loopLineRef.current = null;
    setLoopLineIndex(null);
    if (audioRef.current) audioRef.current.currentTime = start;
    setCurrentTime(start);
    setSegments((prev) => {
      const next = [...prev];
      const currentSeg = { ...next[segIdx] };
      const words = [...getSegmentWords(currentSeg)];
      if (!words[wordIdx]) return prev;

      const clampedVal = Math.max(0, Number(val.toFixed(3)));
      words[wordIdx] = { ...words[wordIdx], [field]: clampedVal, timing_source: "manual", needs_review: false };

      if (field === 'start' && words[wordIdx].start > words[wordIdx].end) {
        words[wordIdx].end = Number((words[wordIdx].start + 0.05).toFixed(3));
      } else if (field === 'end' && words[wordIdx].end < words[wordIdx].start) {
        words[wordIdx].start = Math.max(0, Number((words[wordIdx].end - 0.05).toFixed(3)));
      }

      currentSeg.words = words;
      if (words.length > 0) {
        currentSeg.start = Math.min(currentSeg.start, words[0].start);
        currentSeg.end = Math.max(currentSeg.end, words[words.length - 1].end);
      }
      next[segIdx] = currentSeg;
      triggerAutoSave(next, false);
      return next;
    });
  };

  const handleWordTextChange = (segIdx: number, wordIdx: number, newText: string) => {
    newText = uppercaseLyric(newText);
    setSegments((prev) => {
      const next = [...prev];
      const currentSeg = { ...next[segIdx] };
      const words = [...getSegmentWords(currentSeg)];
      if (!words[wordIdx]) return prev;
      words[wordIdx] = { ...words[wordIdx], word: newText, needs_review: true };
      currentSeg.words = words;
      currentSeg.text = words.map((w) => w.word).join(' ');
      next[segIdx] = currentSeg;
      triggerAutoSave(next, false);
      return next;
    });
  };

  const stepWordTime = (segIdx: number, wordIdx: number, field: 'start' | 'end', delta: number) => {
    const seg = segments[segIdx];
    if (!seg) return;
    const words = getSegmentWords(seg);
    if (!words[wordIdx]) return;
    const curVal = Number(words[wordIdx][field]) || 0;
    handleWordTimeChange(segIdx, wordIdx, field, curVal + delta);
  };

  const setPlayheadToWord = (segIdx: number, wordIdx: number, field: 'start' | 'end') => {
    const cur = Number((wordPlayerRef.current?.playing ? wordPlayerRef.current.currentTime : (audioRef.current?.currentTime || 0)).toFixed(3));
    setSegments((prev) => {
      const next = [...prev];
      const currentSeg = { ...next[segIdx] };
      const words = [...getSegmentWords(currentSeg)];
      if (!words[wordIdx]) return prev;

      words[wordIdx] = { ...words[wordIdx], [field]: cur, timing_source: "manual", needs_review: false };

      currentSeg.words = words;
      if (words.length > 0) {
        currentSeg.start = Math.min(currentSeg.start, words[0].start);
        currentSeg.end = Math.max(currentSeg.end, words[words.length - 1].end);
      }
      next[segIdx] = currentSeg;
      triggerAutoSave(next, false);
      return next;
    });
    onNotify('info', 'Kelime Zamanı Ayarlandı', `Kelime ${field === 'start' ? 'başlangıç' : 'bitiş'} zamanı ${formatPrecisionTime(cur)} yapıldı.`, 1200);
  };

  const playWord = async (segIdx: number, wordIdx: number) => {
    editedPlaybackStartRef.current = null;
    if (loadingLyrics) return;
    const word = segments[segIdx]?.words?.[wordIdx];
    if (!word) return;
    if (activePlayingWord?.segIdx === segIdx && activePlayingWord.wordIdx === wordIdx && wordPlayerRef.current?.playing) {
      stopWordPreview(); setIsPlaying(false); return;
    }
    // A rejected word must not leave the previous word/line playing.
    stopWordPreview();
    audioRef.current?.pause();
    linePreviewEndRef.current = null;
    setActivePlayingIndex(null);
    setIsPlaying(false);
    const requestId = ++wordRequestRef.current;
    try {
      const all = segments.flatMap(seg => seg.words || []);
      const index = all.indexOf(word);
      // An overlap must remain audible while the user repairs it. It still
      // blocks synchronized fill/export through their separate validation.
      checkWordInterval(word);
      if (word.start < (all[index - 1]?.end ?? 0) - 1e-7 || word.end > (all[index + 1]?.start ?? Infinity) + 1e-7) {
        onNotify('warning', 'Kelime süreleri çakışıyor', 'Ayarladığınız aralık çalınıyor; komşu kelime de duyulabilir. Başlangıç ve bitiş sınırlarını kontrol edin.');
      }
      wordPlayerRef.current ??= new WordPlayer();
      const file = vocalStem || instStem;
      const started = await wordPlayerRef.current.play(`/output/${encodeURIComponent(file)}`, word.start, word.end, () => {
        setIsPlaying(false); setActivePlayingWord(null); setCurrentTime(word.end);
        if (audioRef.current) audioRef.current.currentTime = word.end;
      });
      if (!started || requestId !== wordRequestRef.current) return;
      setCurrentTime(word.start);
      setActivePlayingWord({ segIdx, wordIdx });
      setIsPlaying(true);
    } catch (err: any) {
      if (err.name !== 'AbortError' && requestId === wordRequestRef.current) onNotify('warning', 'Kelime dinlenemedi', err.message);
    }
  };

  const distributeWordsEvenly = (segIdx: number) => {
    setSegments((prev) => {
      const next = [...prev];
      const currentSeg = { ...next[segIdx] };
      const rawWords = (currentSeg.text || '').trim().split(/\s+/).filter(Boolean);
      if (rawWords.length === 0) return prev;
      const totalDur = Math.max(0.1, currentSeg.end - currentSeg.start);
      const perWord = totalDur / rawWords.length;
      currentSeg.words = rawWords.map((w, i) => ({
        word: w, timing_source: "estimated" as const, needs_review: true,
        start: Number((currentSeg.start + i * perWord).toFixed(3)),
        end: Number((currentSeg.start + (i + 1) * perWord).toFixed(3)),
      }));
      next[segIdx] = currentSeg;
      triggerAutoSave(next, true);
      return next;
    });
    onNotify('success', 'Eşit Dağıtıldı', 'Kelimeler satır süresi boyunca eşit aralıklarla dağıtıldı.', 1500);
  };

  const distributeWordsBySyllables = (segIdx: number) => {
    setSegments((prev) => {
      const next = [...prev];
      const currentSeg = { ...next[segIdx] };
      const rawWords = (currentSeg.text || '').trim().split(/\s+/).filter(Boolean);
      if (rawWords.length === 0) return prev;

      const vowels = new Set('aeıioöuüAEIİOÖUÜ');
      const weights = rawWords.map((w) => {
        let vCount = 0;
        for (const c of w) { if (vowels.has(c)) vCount++; }
        return Math.max(1, vCount || Math.ceil(w.length * 0.4));
      });
      const totalWeight = weights.reduce((a, b) => a + b, 0) || 1;
      const totalDur = Math.max(0.2, currentSeg.end - currentSeg.start);

      let curStart = currentSeg.start;
      currentSeg.words = rawWords.map((w, i) => {
        const wDur = (weights[i] / totalWeight) * totalDur;
        const wStart = Number(curStart.toFixed(3));
        const wEnd = Number((curStart + wDur).toFixed(3));
        curStart += wDur;
        return { word: w, start: wStart, end: wEnd, timing_source: "estimated" as const, needs_review: true };
      });
      next[segIdx] = currentSeg;
      triggerAutoSave(next, true);
      return next;
    });
    onNotify('success', 'Heceye Göre Dağıtıldı', 'Kelimeler hece uzunluklarına göre akıllıca dağıtıldı.', 1500);
  };

  const handleAddWord = (segIdx: number) => {
    setSegments((prev) => {
      const next = [...prev];
      const currentSeg = { ...next[segIdx] };
      const words = [...getSegmentWords(currentSeg)];
      const lastWord = words[words.length - 1];
      const newStart = lastWord ? lastWord.end : currentSeg.start;
      const newEnd = Number((newStart + 0.5).toFixed(3));
      words.push({ word: 'yeni', start: newStart, end: newEnd });
      currentSeg.words = words;
      currentSeg.text = words.map((w) => w.word).join(' ');
      currentSeg.end = Math.max(currentSeg.end, newEnd);
      next[segIdx] = currentSeg;
      triggerAutoSave(next, true);
      return next;
    });
  };

  const handleDeleteWord = (segIdx: number, wordIdx: number) => {
    setSegments((prev) => {
      const next = [...prev];
      const currentSeg = { ...next[segIdx] };
      const words = getSegmentWords(currentSeg).filter((_, i) => i !== wordIdx);
      currentSeg.words = words;
      currentSeg.text = words.map((w) => w.word).join(' ');
      next[segIdx] = currentSeg;
      triggerAutoSave(next, true);
      return next;
    });
  };

  const handleAddSegment = (index?: number) => {
    if (loadingLyrics) return;
    setSegments((prev) => {
      const next = [...prev];
      if (index !== undefined && next[index]) {
        // Row-level insert (insert right below current row)
        const prevEnd = Number(next[index].end) || 0;
        const nextStart = next[index + 1] ? Number(next[index + 1].start) : prevEnd + 3;
        const newSeg: LyricSegment = {
          start: Number(prevEnd.toFixed(3)),
          end: Number(Math.max(prevEnd + 0.5, nextStart).toFixed(3)),
          text: '',
        };
        next.splice(index + 1, 0, newSeg);
      } else {
        // Top Toolbar "Satır Ekle" Button: Add empty line at the very top (en üste boş satır)
        const firstStart = next.length > 0 ? Number(next[0].start) : 3.0;
        const newSeg: LyricSegment = {
          start: 0.0,
          end: Number(Math.max(0.5, firstStart).toFixed(3)),
          text: '',
        };
        next.unshift(newSeg);
      }
      triggerAutoSave(next, true);
      return next;
    });
  };

  const handleDeleteSegment = (index: number) => {
    setSegments((prev) => {
      const next = prev.filter((_, i) => i !== index);
      triggerAutoSave(next, true);
      return next;
    });
  };

  // Export Lyrics to JSON, LRC or SRT file
  const handleExport = (format: 'json' | 'lrc' | 'srt') => {
    if (segments.length === 0) {
      onNotify('warning', 'Dışa Aktarılacak Söz Yok', 'Lütfen önce en az bir satır söz ekleyin.');
      return;
    }

    const baseName = (instStem || vocalStem || 'karaoke_lyrics').replace(/\.[^/.]+$/, '').replace(/_(Instrumental|Vocals|other).*/i, '');
    let content = '';
    let mimeType = 'text/plain;charset=utf-8';
    const fileExt = format;

    if (format === 'json') {
      content = serializeProject(segments, { title, artist, duration, source_file: vocalStem || instStem });
      mimeType = 'application/json;charset=utf-8';
    } else if (format === 'lrc') {
      const lines = [
        `[ti:${title || baseName}]`,
        `[ar:${artist || 'UVR5 Studio'}]`,
        `[length:${formatPrecisionTime(duration)}]`,
      ];
      segments.forEach((s) => {
        const startSec = Number(s.start) || 0;
        const mins = Math.floor(startSec / 60);
        const secs = (startSec % 60).toFixed(3).padStart(5, '0');
        lines.push(`[${mins.toString().padStart(2, '0')}:${secs}]${s.text.trim()}`);
      });
      content = lines.join('\n');
    } else if (format === 'srt') {
      const srtBlocks = segments.map((s, idx) => {
        const stSec = Number(s.start) || 0;
        const enSec = Number(s.end) || stSec + 2.0;

        const stH = Math.floor(stSec / 3600);
        const stM = Math.floor((stSec % 3600) / 60);
        const stS = Math.floor(stSec % 60);
        const stMs = Math.floor((stSec - Math.floor(stSec)) * 1000);

        const enH = Math.floor(enSec / 3600);
        const enM = Math.floor((enSec % 3600) / 60);
        const enS = Math.floor(enSec % 60);
        const enMs = Math.floor((enSec - Math.floor(enSec)) * 1000);

        const stStr = `${stH.toString().padStart(2, '0')}:${stM.toString().padStart(2, '0')}:${stS.toString().padStart(2, '0')},${stMs.toString().padStart(3, '0')}`;
        const enStr = `${enH.toString().padStart(2, '0')}:${enM.toString().padStart(2, '0')}:${enS.toString().padStart(2, '0')},${enMs.toString().padStart(3, '0')}`;

        return `${idx + 1}\n${stStr} --> ${enStr}\n${s.text.trim()}\n`;
      });
      content = srtBlocks.join('\n');
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${baseName}_lyrics.${fileExt}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Let the browser finish consuming the download before releasing its blob.
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);

    onNotify('success', 'Dışa Aktarıldı (Export) 📤', `${segments.length} satır söz ve süre ${format.toUpperCase()} formatında indirildi.`);
    setShowExportMenu(false);
  };

  // Import Lyrics from JSON, LRC or SRT file
  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (loadingLyrics) return;
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const fileName = file.name.toLowerCase();
      let importedSegments: LyricSegment[] = [];

      if (fileName.endsWith('.json')) {
        importedSegments = importProject(text);
      } else if (fileName.endsWith('.lrc')) {
        const lines = text.split(/\r?\n/);
        const lrcEntries: { start: number; text: string }[] = [];
        const timeRegex = /\[(\d{2}):(\d{2})(?:\.(\d{2,3}))?\]/g;

        lines.forEach((line) => {
          const matches = [...line.matchAll(timeRegex)];
          const cleanText = line.replace(timeRegex, '').trim();
          if (cleanText) {
            matches.forEach((m) => {
              const mins = parseInt(m[1], 10) || 0;
              const secs = parseInt(m[2], 10) || 0;
              const frac = m[3] ? parseFloat(`0.${m[3]}`) : 0;
              const totalSec = mins * 60 + secs + frac;
              lrcEntries.push({ start: Number(totalSec.toFixed(3)), text: cleanText });
            });
          }
        });

        lrcEntries.sort((a, b) => a.start - b.start);
        importedSegments = lrcEntries.map((entry, idx) => {
          const nextStart = lrcEntries[idx + 1] ? lrcEntries[idx + 1].start : entry.start + 3.0;
          return {
            start: entry.start,
            end: Number(Math.max(entry.start + 0.5, nextStart - 0.2).toFixed(3)),
            text: entry.text,
          };
        });
      } else if (fileName.endsWith('.srt')) {
        const blocks = text.split(/\r?\n\r?\n/);
        blocks.forEach((block) => {
          const lines = block.trim().split(/\r?\n/);
          if (lines.length >= 2) {
            const timeLine = lines.find((l) => l.includes('-->'));
            if (timeLine) {
              const [stStr, enStr] = timeLine.split('-->').map((s) => s.trim());
              const parseSrtTime = (tStr: string) => {
                const parts = tStr.replace(',', '.').split(':');
                if (parts.length === 3) {
                  return parseInt(parts[0], 10) * 3600 + parseInt(parts[1], 10) * 60 + parseFloat(parts[2]);
                }
                return 0;
              };
              const start = Number(parseSrtTime(stStr).toFixed(3));
              const end = Number(parseSrtTime(enStr).toFixed(3));
              const textLines = lines.slice(lines.indexOf(timeLine) + 1).join(' ').trim();
              if (textLines) {
                importedSegments.push({ start, end, text: textLines });
              }
            }
          }
        });
      } else {
        const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l.length > 0);
        if (lines.length > 0) {
          const totalDur = duration > 0 ? duration : lines.length * 4.0;
          const step = totalDur / lines.length;
          importedSegments = lines.map((l, idx) => ({
            start: Number((idx * step).toFixed(3)),
            end: Number(((idx + 1) * step - 0.3).toFixed(3)),
            text: l,
          }));
        }
      }

      if (importedSegments.length > 0) {
        const capitalized = uppercaseLyrics(importedSegments);
        setSegments(capitalized);
        triggerAutoSave(capitalized, true);
        onNotify('success', 'İçe Aktarıldı & Kaydedildi (Import) 📥', `${importedSegments.length} satır söz ve süreler yüklendi ve SQLite veritabanına kalıcı olarak kaydedildi.`);
      } else {
        onNotify('warning', 'Dosya Boş', 'Dosyada geçerli şarkı sözü satırı bulunamadı.');
      }
    } catch (err: any) {
      onNotify('error', 'İçe Aktarma Hatası', err.message || 'Dosya okunamadı.');
    } finally {
      if (importFileInputRef.current) importFileInputRef.current.value = '';
    }
  };

  // Playback Controls
  const toggleMasterPlay = () => {
    stopWordPreview();
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      wordPreviewEndRef.current = null;
      linePreviewEndRef.current = null;
      setActivePlayingWord(null);
      setActivePlayingIndex(null);
    } else {
      // Clear word or line preview limits when master play is clicked so entire song plays continuously
      loopLineRef.current = null;
      setLoopLineIndex(null);
      if (editedPlaybackStartRef.current !== null) {
        audioRef.current.currentTime = editedPlaybackStartRef.current;
        setCurrentTime(editedPlaybackStartRef.current);
        if(isLiveSyncMode&&liveGesture==='tap')liveCaptureRef.current={index:liveSyncIndex,start:editedPlaybackStartRef.current};
        editedPlaybackStartRef.current = null;
      }
      wordPreviewEndRef.current = null;
      linePreviewEndRef.current = null;
      setActivePlayingWord(null);
      audioRef.current.play().catch(() => {});
    }
  };

  const stepCurrentTime = (delta: number) => {
    editedPlaybackStartRef.current = null;
    stopWordPreview();
    if (!audioRef.current) return;
    const newT = Math.max(0, Math.min(duration, audioRef.current.currentTime + delta));
    audioRef.current.currentTime = newT;
    setCurrentTime(newT);
    if(isLiveSyncMode&&liveGesture==='tap')liveCaptureRef.current={index:liveSyncIndex,start:newT};
  };

  const seekTo = (targetSec: number) => {
    liveCaptureRef.current=null;setIsSpacePressed(false);
    editedPlaybackStartRef.current = null;
    stopWordPreview();
    if (!audioRef.current) return;
    const clamped = Math.max(0, Math.min(duration || 9999, targetSec));
    audioRef.current.currentTime = clamped;
    setCurrentTime(clamped);
    // A live seek selects the new row start now, not on the next Space press.
    if(isLiveSyncMode&&liveGesture==='tap')liveCaptureRef.current={index:liveSyncIndex,start:clamped};
  };

  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!progressBarRef.current || duration <= 0) return;
    const rect = progressBarRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const fraction = Math.max(0, Math.min(1, clickX / rect.width));
    seekTo(fraction * duration);
  };

  const handleTimelineMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!progressBarRef.current || duration <= 0) return;
    const rect = progressBarRef.current.getBoundingClientRect();
    const moveX = e.clientX - rect.left;
    const fraction = Math.max(0, Math.min(1, moveX / rect.width));
    setHoverTime(fraction * duration);
  };

  const playLine = (index: number) => {
    editedPlaybackStartRef.current = null;
    stopWordPreview();
    if (!audioRef.current || !segments[index]) return;
    const seg = rowPlaybackRange(segments[index]);
    // A loop on another row must not seek away from this row during playback.
    if (loopLineIndex !== index) {
      loopLineRef.current = null;
      setLoopLineIndex(null);
    }

    if (activePlayingIndex === index && isPlaying) {
      audioRef.current.pause();
      setActivePlayingIndex(null);
      linePreviewEndRef.current = null;
      return;
    }

    wordPreviewEndRef.current = null;
    setActivePlayingWord(null);

    // If loop is not active, set auto-stop at line end (+ 0.05s buffer)
    if (loopLineIndex !== index) {
      linePreviewEndRef.current = seg.end;
    } else {
      linePreviewEndRef.current = null;
    }

    audioRef.current.currentTime = seg.start;
    setCurrentTime(seg.start);
    audioRef.current.play().catch(() => {});
    setActivePlayingIndex(index);
  };

  const playRow = (index: number) => {
    playLine(index);
  };

  const stepSegmentTime = (index: number, field: 'start' | 'end', delta: number) => {
    setSegments((prev) => {
      const next = [...prev];
      if (!next[index]) return prev;
      const currentVal = Number(next[index][field]) || 0;
      const newVal = Math.max(0, Number((currentVal + delta).toFixed(3)));
      const updated = { ...next[index], [field]: newVal };
      const s = Number(updated.start) || 0;
      const e = Number(updated.end) || (s + 2.0);
      updated.words = fitWordsToSegmentRange(
        updated.words || [],
        s,
        Math.max(s + 0.1, e),
        updated.text || ''
      );
      next[index] = updated;
      triggerAutoSave(next, true);
      return next;
    });
  };

  const setPlayheadToSegment = (index: number, field: 'start' | 'end') => {
    const cur = Number((wordPlayerRef.current?.playing ? wordPlayerRef.current.currentTime : (audioRef.current?.currentTime || 0)).toFixed(3));
    setSegments((prev) => {
      const next = [...prev];
      if (!next[index]) return prev;
      const updated = { ...next[index] };

      if (field === 'start') {
        updated.start = cur;
        // Automatically set end time to at least start + 15.0s
        updated.end = Math.max(updated.end, cur + 0.001);
      } else {
        updated.end = cur;
      }

      const s = Number(updated.start) || 0;
      const e = Number(updated.end) || (s + 2.0);
      updated.words = fitWordsToSegmentRange(
        updated.words || [],
        s,
        Math.max(s + 0.1, e),
        updated.text || ''
      );
      next[index] = updated;

      triggerAutoSave(next, true);
      return next;
    });

    if (field === 'start') {
      onNotify('info', 'Başlangıç Ayarlandı ⏱️', `Satır başlangıcı ${formatPrecisionTime(cur)} olarak güncellendi. Kelime zamanları korundu.`, 2400);
    } else if (field === 'end' && index < segments.length - 1) {
      onNotify('info', 'Bitiş Ayarlandı', `Satır bitişi ${formatPrecisionTime(cur)} olarak güncellendi. Sonraki satır korundu.`, 2200);
    } else {
      onNotify('info', 'Zaman Ayarlandı', `Bitiş zamanı ${formatPrecisionTime(cur)} olarak güncellendi.`, 1800);
    }
  };

  const toggleLoopLine = (index: number) => {
    if (loopLineIndex === index) {
      setLoopLineIndex(null);
    } else {
      setLoopLineIndex(index);
      if (segments[index]) {
        seekTo(rowPlaybackRange(segments[index]).start);
        if (audioRef.current && !isPlaying) {
          audioRef.current.play().catch(() => {});
        }
      }
    }
  };

  const formatPrecisionTime = (seconds: number) => {
    if (!Number.isFinite(seconds) || seconds < 0) return '00:00.000';
    const ms = Math.round(seconds * 1000);
    return `${Math.floor(ms / 60000).toString().padStart(2, '0')}:${Math.floor(ms / 1000 % 60).toString().padStart(2, '0')}.${(ms % 1000).toString().padStart(3, '0')}`;
  };

  const handleGenerateVideo = async () => {
    if (segments.length === 0) {
      onNotify('warning', 'Söz Eksik', 'Lütfen en az bir şarkı sözü satırı ekleyin.');
      return;
    }

    const issues = timingIssues(videoSegments(segments), false, false);
    if (issues.length) { onNotify("warning", "Önce kelime zamanlarını hizalayın", issues.slice(0, 3).join(" / ")); return; }
    stopWordPreview();
    if (audioRef.current) audioRef.current.pause();
    setRendering(true);
    setRenderStatusMsg('Karaoke Altyazıları & Render Hazırlanıyor...');
    setVideoUrl(null);
    try {
      const finalizedSegments = structuredClone(segments);
      flushPendingSave();
      await saveToDatabase(finalizedSegments, false);

      const res = await api.generateKaraokeVideo({
        inst_file: instStem,
        timing_file: vocalStem || instStem,
        segments: videoSegments(finalizedSegments),
        title: title,
        artist: artist,
        header_text: headerPrefix,
        show_header: showHeader,
        aspect_ratio: aspectRatio,
        theme: theme,
      }, (msg) => {
        setRenderStatusMsg(msg);
      });

      if (res.download_url) {
        setVideoUrl(res.download_url);
        setVideoFilename(res.video_file || 'karaoke_video_1080p.mp4');
        setActiveTab('video');
        onNotify('success', '🎬 1080p Karaoke Videosu Hazır!', 'Videonuz başarıyla oluşturuldu.');
      }
    } catch (err: any) {
      onNotify('error', 'Render Başarısız', err.message || 'Karaoke videosu oluşturulamadı');
    } finally {
      setRendering(false);
      setRenderStatusMsg('FFmpeg 1080p Render Ediliyor...');
    }
  };

  const syncIssues = timingIssues(segments);
  const renderErrors = timingIssues(videoSegments(segments), false, false);

  if (!isOpen || !mounted) return null;

  const currentSyncSegment = segments[liveSyncIndex];

  return createPortal(
    <div className="fixed inset-0 z-[99999] flex items-center justify-center p-1.5 sm:p-3 bg-[#050608]/95 backdrop-blur-2xl animate-fade-in">
      <div className="relative w-full max-w-[1840px] bg-[#1b1823] border border-white/10 rounded-[22px] shadow-2xl overflow-hidden flex flex-col h-[97dvh] max-h-[97dvh]">
        {/* Modal Header */}
        <div className="px-5 sm:px-8 py-3 shrink-0 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-amber-400/10 text-amber-300 border border-amber-400/15">
              <Video className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold font-outfit text-white tracking-tight">
                  Karaoke Stüdyosu
                </h3>
                <span className="text-[9px] font-bold font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20">
                  1080P HD
                </span>
              </div>
              <p className="text-xs text-zinc-400 truncate max-w-[55vw] sm:max-w-md">
                Enstrümantal: <span className="text-slate-200 font-bold">{instStem}</span>
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              if (audioRef.current) audioRef.current.pause();
              onClose();
            }}
            className="p-2 rounded-xl bg-white/[0.05] hover:bg-white/10 text-zinc-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav aria-label="Karaoke adımları" className="grid grid-cols-3 gap-3 shrink-0 border-b border-white/[0.06] px-5 py-2 sm:px-8">
          {([{key: 'verify', label: 'Sözleri doğrula', detail: 'Metni bul ve düzenle'}, {key: 'lyrics', label: 'Senkronu kontrol et', detail: 'Dinle ve kelimeleri ayarla'}, {key: 'video', label: 'Videoyu oluştur', detail: 'Görünümü seç ve indir'}] as const).map((step, index) => (
            <button key={step.key} type="button" aria-current={activeTab === step.key ? 'step' : undefined} onClick={() => {setActiveTab(step.key); setShowAdvancedTools(false); if(step.key==='video'){audioRef.current?.pause();stopWordPreview();liveCaptureRef.current=null;setIsLiveSyncMode(false);}}} className={cn('flex items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors', activeTab === step.key ? 'bg-white/[0.06] text-amber-200 ring-1 ring-white/10' : 'text-zinc-400 hover:bg-white/5 hover:text-slate-200')}>
              <span className={cn('hidden h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold sm:flex', activeTab === step.key ? 'bg-amber-400 text-slate-950' : 'bg-white/5')}>{index + 1}</span>
              <span><span className="block text-xs font-semibold sm:text-sm"><span className="sm:hidden">{index + 1}. </span>{step.label}</span><span className="sr-only">{step.detail}</span></span>
            </button>
          ))}
        </nav>
        {activeTab !== 'video' && <div className="flex flex-wrap shrink-0 items-center justify-between gap-3 border-b border-white/5 px-4 py-2 sm:px-6">
          <div className="min-w-0">
            <h4 className="font-semibold text-slate-100">{activeTab === 'verify' ? 'Önce doğru sözler.' : 'Her kelime, kendi zamanında.'}</h4>
            <p className="sr-only">{activeTab === 'verify' ? 'Referans sözleri karşılaştır veya satırları doğrudan düzenle.' : 'Bir kelimeye dokun: dinle, renk dolmasını kontrol et ve gerekirse ayarla.'}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button disabled={loadingLyrics || !!bulkBindingStatus || !segments.length} onClick={()=>void bindEveryRow()} className="rounded-lg border border-pink-400/30 bg-pink-400/10 px-3 py-2 text-sm font-semibold text-pink-200 hover:bg-pink-400/20 disabled:opacity-40">{bulkBindingStatus || 'Tüm satırların ses parçalarını bağla'}</button>
            <button disabled={loadingLyrics || !segments.length} onClick={() => activeTab === 'verify' ? setShowReferenceModal(true) : void fetchInitialLyrics(vocalStem || instStem, true, whisperModel, segments.map(s => s.text).join('\n')).catch(() => {})} className="rounded-lg bg-amber-400 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">{loadingLyrics ? 'İşleniyor…' : activeTab === 'verify' ? 'Sözleri bul ve karşılaştır' : 'Otomatik hizala'}</button>
            <button aria-expanded={showAdvancedTools} aria-controls="karaoke-tools" onClick={() => setShowAdvancedTools(!showAdvancedTools)} className={cn("rounded-lg border px-3 py-2 text-sm transition-colors", showAdvancedTools ? "border-indigo-400/30 bg-indigo-400/10 text-indigo-200" : "border-white/10 text-zinc-200 hover:bg-white/5")}>Diğer araçlar <ChevronDown className={cn("ml-1 inline h-3 w-3 transition-transform", showAdvancedTools && "rotate-180")}/></button>
          </div>
        </div>}
        {activeTab === 'lyrics' && (renderErrors.length > 0 || syncIssues.length > 0) && <div role="status" className="flex items-center justify-between gap-3 border-b border-white/5 bg-amber-400/5 px-6 py-2 text-xs text-amber-200">
          <span>{renderErrors.length ? `${renderErrors.length} zamanlama sorunu · ${renderErrors[0]}` : `${syncIssues.length} kelimenin zamanı doğrulanmamış. Eksik kelime süreleri olan satırlar videoda satır olarak gösterilir. Video oluşturabilirsin.`}</span>
          <button className="shrink-0 underline underline-offset-4" onClick={() => {
            const row = segments.findIndex(s => (s.words || []).some(w => w.needs_review || w.timing_source === 'estimated' || w.end <= w.start));
            if (row >= 0) {setExpandedWordRow(row); setSelectedWordIndex(Math.max(0, (segments[row].words || []).findIndex(w => w.needs_review || w.timing_source === 'estimated' || w.end <= w.start))); rowRefs.current[row]?.scrollIntoView({block: 'center', behavior: 'smooth'});}
          }}>İlk uyarıya git</button>
        </div>}

        {activeTab !== 'video' && bulkBindingProblems.length>0 && <details className="shrink-0 border-b border-amber-400/15 px-6 py-2 text-xs text-amber-200"><summary className="cursor-pointer">{bulkBindingProblems.length} satır bağlanamadı · Ayrıntıları göster</summary><ul className="mt-2 max-h-28 overflow-y-auto space-y-1">{bulkBindingProblems.map(problem=><li key={problem}>{problem}</li>)}</ul></details>}
        {/* Secondary Action Toolbar (for Lyrics Tab) */}
        {activeTab !== 'video' && showAdvancedTools && (
          <div id="karaoke-tools" role="region" aria-label="Diğer karaoke araçları" className="shrink-0 max-h-[32dvh] overflow-y-auto custom-scrollbar border-b border-white/[0.07] bg-indigo-300/[0.025] px-4 py-4 sm:px-6 [&_button]:min-h-9">
            <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr_1.5fr]">
            <div className="space-y-3">
            <h4 className="text-xs font-semibold text-zinc-400">Canlı zamanlama</h4>
            <button onClick={() => isLiveSyncMode ? setIsLiveSyncMode(false) : (setShowAdvancedTools(false), setActiveTab('lyrics'), startLiveSyncMode(liveSyncIndex))} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-zinc-200">{isLiveSyncMode ? 'Canlı senkronu kapat' : 'Boşluk tuşuyla canlı senkron'}</button>
            {segments.length > 0 && <button onClick={undoAllLiveSync} className="block rounded-lg border border-rose-400/20 px-3 py-2 text-xs text-rose-200 hover:bg-rose-400/10">Tüm zamanlamaları temizle</button>}
            </div>
            {/* Left Group: Whisper AI Controls */}
            <div className="flex content-start items-center flex-wrap gap-2">
              <h4 className="mb-1 w-full text-xs font-semibold text-zinc-400">Sesten sözleri çıkar</h4>
              {/* Whisper AI Model Selector Dropdown */}
              <div className="relative" ref={whisperMenuRef}>
                <button
                  onClick={() => setShowWhisperMenu(!showWhisperMenu)}
                  className="px-3 py-1.5 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold flex items-center gap-1.5 transition-all active:scale-95 shadow-sm cursor-pointer"
                  title="Kullanılacak Whisper Yapay Zeka Modelini Seçin"
                >
                  {whisperModel === 'large-v3' ? (
                    <Crown className="w-3.5 h-3.5 text-amber-400" />
                  ) : (
                    <Zap className="w-3.5 h-3.5 text-indigo-400" />
                  )}
                  <span>{whisperModel === 'large-v3' ? 'Large-V3 (Full HQ)' : 'Large-V3-Turbo'}</span>
                  <ChevronDown className="w-3 h-3 opacity-60 ml-0.5" />
                </button>

                {showWhisperMenu && (
                  <KaraokeToolPopover anchor={whisperMenuRef} width={288} onClose={() => setShowWhisperMenu(false)}>
                    <div className="px-2.5 py-1 text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                      Whisper Yapay Zeka Modeli
                    </div>
                    <button
                      onClick={() => {
                        setWhisperModel('large-v3');
                        setShowWhisperMenu(false);
                        void fetchInitialLyrics(vocalStem || instStem, true, 'large-v3').catch(() => {});
                      }}
                      className={cn(
                        'w-full p-2.5 rounded-xl text-left transition-all flex items-start gap-2.5 cursor-pointer',
                        whisperModel === 'large-v3'
                          ? 'bg-amber-500/15 border border-amber-500/30 text-white'
                          : 'hover:bg-white/5 text-zinc-200'
                      )}
                    >
                      <Crown className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-bold">Whisper Large-V3</span>
                          <span className="text-[9px] font-bold bg-amber-400/20 text-amber-300 px-1.5 py-0.2 rounded border border-amber-400/30">
                            FULL HQ
                          </span>
                        </div>
                        <p className="text-[10px] text-zinc-400 mt-0.5 leading-tight">
                          32 Katman • 1.55B Parametre • Tüm sözleri eksiksiz çıkarır
                        </p>
                      </div>
                    </button>

                    <button
                      onClick={() => {
                        setWhisperModel('large-v3-turbo');
                        setShowWhisperMenu(false);
                        void fetchInitialLyrics(vocalStem || instStem, true, 'large-v3-turbo').catch(() => {});
                      }}
                      className={cn(
                        'w-full p-2.5 rounded-xl text-left transition-all flex items-start gap-2.5 cursor-pointer',
                        whisperModel === 'large-v3-turbo'
                          ? 'bg-indigo-500/15 border border-indigo-500/30 text-white'
                          : 'hover:bg-white/5 text-zinc-200'
                      )}
                    >
                      <Zap className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-bold">Whisper Large-V3-Turbo</span>
                          <span className="text-[9px] font-bold bg-indigo-400/20 text-indigo-300 px-1.5 py-0.2 rounded border border-indigo-400/30">
                            HIZLI
                          </span>
                        </div>
                        <p className="text-[10px] text-zinc-400 mt-0.5 leading-tight">
                          4 Katman • ~4x Hızlı transkripsiyon
                        </p>
                      </div>
                    </button>
                  </KaraokeToolPopover>
                )}
              </div>

              {/* Whisper Language Selector Dropdown */}
              <div className="relative" ref={langMenuRef}>
                <button
                  onClick={() => setShowLangMenu(!showLangMenu)}
                  className="px-3 py-1.5 rounded-xl bg-teal-500/10 hover:bg-teal-500/20 text-teal-300 border border-teal-500/30 text-xs font-bold flex items-center gap-1.5 transition-all active:scale-95 shadow-sm cursor-pointer"
                  title="Şarkı Sözü Algılama Dilini Değiştirin"
                >
                  <Globe className="w-3.5 h-3.5 text-teal-400" />
                  <span>
                    {(() => {
                      const activeL = WHISPER_LANGUAGES.find((l) => l.code === selectedLyricsLang);
                      return activeL ? `${activeL.flag} ${activeL.name.split(' (')[0]}` : `🌐 ${selectedLyricsLang}`;
                    })()}
                  </span>
                  <ChevronDown className="w-3 h-3 opacity-60 ml-0.5" />
                </button>

                {showLangMenu && (
                  <KaraokeToolPopover anchor={langMenuRef} width={320} onClose={() => setShowLangMenu(false)}>
                    <div className="flex items-center justify-between px-1">
                      <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                        Şarkı Sözü Dili (Whisper AI)
                      </span>
                      <span className="text-[9px] text-teal-400 font-mono">99+ Dil Destekli</span>
                    </div>

                    {/* Search Filter for Languages */}
                    <div className="relative">
                      <input
                        type="text"
                        value={langSearchQuery}
                        onChange={(e) => setLangSearchQuery(e.target.value)}
                        placeholder="Dil ara... (Türkçe, English, 한국어, العربية...)"
                        className="w-full bg-[#14121c]/90 border border-white/10 focus:border-teal-500/50 rounded-xl px-3 py-1.5 text-xs text-white placeholder-slate-500 outline-none"
                        autoFocus
                      />
                    </div>

                    {/* Scrollable Language List */}
                    <div className="max-h-64 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                      {WHISPER_LANGUAGES.filter(
                        (l) =>
                          !langSearchQuery ||
                          l.name.toLowerCase().includes(langSearchQuery.toLowerCase()) ||
                          l.native.toLowerCase().includes(langSearchQuery.toLowerCase()) ||
                          l.code.toLowerCase().includes(langSearchQuery.toLowerCase())
                      ).map((langItem) => {
                        const isSelected = selectedLyricsLang === langItem.code;
                        return (
                          <button
                            key={langItem.code}
                            onClick={() => {
                              setSelectedLyricsLang(langItem.code);
                              setShowLangMenu(false);
                              setLangSearchQuery('');
                              fetchInitialLyrics(
                                vocalStem || instStem,
                                true,
                                whisperModel,
                                undefined,
                                langItem.code
                              ).catch(() => {});
                            }}
                            className={cn(
                              'w-full px-3 py-2 rounded-xl text-left transition-all flex items-center justify-between text-xs cursor-pointer',
                              isSelected
                                ? 'bg-teal-500/20 border border-teal-500/40 text-teal-200 font-bold'
                                : 'hover:bg-white/5 text-zinc-200 font-medium'
                            )}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-base leading-none">{langItem.flag}</span>
                              <span className="truncate">{langItem.name}</span>
                              {langItem.native !== langItem.name && (
                                <span className="text-[10px] text-zinc-400 truncate font-normal">
                                  ({langItem.native})
                                </span>
                              )}
                            </div>
                            {isSelected && <Check className="w-3.5 h-3.5 text-teal-400 shrink-0 ml-2" />}
                          </button>
                        );
                      })}
                    </div>
                  </KaraokeToolPopover>
                )}
              </div>

              {/* Re-transcribe Button */}
              <button
                onClick={() => void fetchInitialLyrics(vocalStem || instStem, true, whisperModel, undefined, selectedLyricsLang).catch(() => {})}
                disabled={loadingLyrics}
                title="Seçili dil ve Whisper AI modeli ile şarkı sözlerini sıfırdan baştan analiz et"
                className="px-3 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-bold flex items-center gap-1.5 transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
              >
                {loadingLyrics ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5" />
                )}
                <span>AI ile Yeniden Çıkar</span>
              </button>
            </div>

            {/* Right Group: Paste, Import, Export, Add Segment */}
            <div className="flex content-start items-center flex-wrap gap-2">
              <h4 className="mb-1 w-full text-xs font-semibold text-zinc-400">Sözler ve dosyalar</h4>
              <button type="button" disabled={loadingLyrics || !segments.length} onClick={() => setShowReferenceModal(true)} className="rounded-xl border border-indigo-500/40 px-3 py-2 text-xs font-bold text-indigo-300 disabled:opacity-40">Sözleri bul ve doğrula</button>
              {/* Paste & Auto-Align Lyrics Button */}
              <button
                onClick={() => setShowPasteModal(true)}
                className="px-3 py-1.5 rounded-xl bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-bold flex items-center gap-1.5 transition-all active:scale-95 shadow-sm cursor-pointer"
                title="Şarkının gerçek sözlerini yapıştırıp yapay zeka ile otomatik zamanla"
              >
                <ClipboardPaste className="w-3.5 h-3.5 text-purple-400" />
                <span>Söz Yapıştır & Senkronla</span>
              </button>

              {/* Hidden File Input for Importing Lyrics */}
              <input
                ref={importFileInputRef}
                type="file"
                accept=".json,.lrc,.srt,.txt"
                className="hidden"
                onChange={handleImportFile}
              />

              {/* Import Lyrics Button */}
              <button
                onClick={() => importFileInputRef.current?.click()}
                className="px-3 py-1.5 rounded-xl bg-teal-500/10 hover:bg-teal-500/20 text-teal-300 border border-teal-500/30 text-xs font-bold flex items-center gap-1.5 transition-all active:scale-95 shadow-sm cursor-pointer"
                title="JSON, LRC veya SRT formatındaki söz ve süreleri içe aktar"
              >
                <FolderUp className="w-3.5 h-3.5 text-teal-400" />
                <span>İçe Aktar</span>
              </button>

              {/* Export Lyrics Dropdown Menu */}
              <div className="relative" ref={exportMenuRef}>
                <button
                  onClick={() => setShowExportMenu(!showExportMenu)}
                  className="px-3 py-1.5 rounded-xl bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-bold flex items-center gap-1.5 transition-all active:scale-95 shadow-sm cursor-pointer"
                  title="Şarkı sözlerini ve milisaniye sürelerini JSON, LRC veya SRT olarak dışa aktar / yedekle"
                >
                  <FolderDown className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Dışa Aktar</span>
                  <ChevronDown className="w-3 h-3 opacity-60 ml-0.5" />
                </button>

                {showExportMenu && (
                  <KaraokeToolPopover anchor={exportMenuRef} width={224} onClose={() => setShowExportMenu(false)}>
                    <div className="px-3 py-1.5 text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                      Format Seçin (Export)
                    </div>
                    <button
                      onClick={() => handleExport('json')}
                      className="w-full px-3 py-2 rounded-xl text-xs font-semibold text-slate-200 hover:text-white hover:bg-white/10 flex items-center justify-between transition-colors group"
                    >
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded-md bg-indigo-500/20 text-indigo-400 font-mono text-[10px] font-bold">JSON</span>
                        <span>JSON Formatı</span>
                      </div>
                      <span className="text-[10px] text-amber-400 font-bold bg-amber-500/10 px-1.5 py-0.5 rounded">Önerilen</span>
                    </button>
                    <button
                      onClick={() => handleExport('lrc')}
                      className="w-full px-3 py-2 rounded-xl text-xs font-semibold text-slate-200 hover:text-white hover:bg-white/10 flex items-center justify-between transition-colors group"
                    >
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded-md bg-pink-500/20 text-pink-400 font-mono text-[10px] font-bold">LRC</span>
                        <span>LRC Karaoke</span>
                      </div>
                    </button>
                    <button
                      onClick={() => handleExport('srt')}
                      className="w-full px-3 py-2 rounded-xl text-xs font-semibold text-slate-200 hover:text-white hover:bg-white/10 flex items-center justify-between transition-colors group"
                    >
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded-md bg-emerald-500/20 text-emerald-400 font-mono text-[10px] font-bold">SRT</span>
                        <span>SRT Altyazı</span>
                      </div>
                    </button>
                  </KaraokeToolPopover>
                )}
              </div>

              {/* Add Segment */}
              <button
                onClick={() => handleAddSegment()}
                className="px-3 py-1.5 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold flex items-center gap-1.5 transition-all active:scale-95 cursor-pointer"
                title="En başa yeni boş satır ekle"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Satır Ekle</span>
              </button>
            </div>
            </div>
          </div>
        )}

        {/* Tab 1: Interactive Lyric Editor with Pro Studio Timeline Scrubber */}
        {activeTab !== 'video' && (
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            {/* Master Precision Audio Player & Timeline Progress Bar (Pinned / Sticky Top) */}
            <div className="px-5 sm:px-8 py-3 bg-[#191621] border-b border-white/5 shrink-0 z-20 space-y-2">
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  {/* Left: Master Play / Rewind / Fast-Forward */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => stepCurrentTime(-2)}
                      className="px-2.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-200 transition-all active:scale-95 text-xs font-bold flex items-center gap-1 border border-white/5"
                      title="2 Saniye Geri Sar"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>-2s</span>
                    </button>

                    <button
                      onClick={toggleMasterPlay}
                      className={cn(
                        "px-4 py-2 rounded-xl font-black text-xs flex items-center gap-2 shadow-lg transition-all active:scale-95",
                        isPlaying
                          ? "bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-amber-500/20"
                          : "bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 shadow-amber-500/20"
                      )}
                    >
                      {isPlaying ? (
                        <>
                          <Pause className="w-4 h-4 fill-current" />
                          <span>Durdur</span>
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 fill-current ml-0.5" />
                          <span>Oynat</span>
                        </>
                      )}
                    </button>

                    <button
                      onClick={() => stepCurrentTime(2)}
                      className="px-2.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-200 transition-all active:scale-95 text-xs font-bold flex items-center gap-1 border border-white/5"
                      title="2 Saniye İleri Sar"
                    >
                      <FastForward className="w-3.5 h-3.5" />
                      <span>+2s</span>
                    </button>
                  </div>

                  {/* Center: Audio Source Selection (Vocal vs Instrumental) */}
                  <div className="flex items-center gap-1 bg-[#262230]/90 p-1 rounded-xl border border-white/5">
                    <span className="text-[10px] font-bold text-zinc-400 px-2 uppercase font-mono">Ses:</span>
                    {vocalStem && (
                      <button
                        onClick={() => setActiveAudioSource('vocal')}
                        className={cn(
                          "px-2.5 py-1 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all",
                          activeAudioSource === 'vocal'
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/30 shadow-sm"
                            : "text-zinc-400 hover:text-white"
                        )}
                        title="Söz senkronu yaparken sadece insan sesini net duyun"
                      >
                        <Mic2 className="w-3 h-3" />
                        <span>Vokal (İnsan Sesi)</span>
                      </button>
                    )}
                    <button
                      onClick={() => setActiveAudioSource('inst')}
                      className={cn(
                        "px-2.5 py-1 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all",
                        activeAudioSource === 'inst'
                          ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 shadow-sm"
                          : "text-zinc-400 hover:text-white"
                      )}
                      title="Müziğin ritmini ve enstrümantal halini dinleyin"
                    >
                      <Music className="w-3 h-3" />
                      <span>Enstrümantal</span>
                    </button>
                  </div>

                  {/* Right: Real-time Millisecond Clock */}
                  <div className="flex items-center gap-2 font-mono text-xs">
                    <span className="text-amber-300 font-black text-sm bg-[#14121c] px-3 py-1 rounded-xl border border-amber-500/30 shadow-inner">
                      ⏱️ {formatPrecisionTime(currentTime)}
                    </span>
                    <span className="text-zinc-400 font-bold">/</span>
                    <span className="text-slate-200 font-bold text-xs">{formatPrecisionTime(duration)}</span>
                  </div>
                </div>

                {/* Interactive Scrubbable Timeline Track */}
                <div
                  ref={progressBarRef}
                  onClick={handleTimelineClick}
                  onMouseMove={handleTimelineMouseMove}
                  onMouseLeave={() => setHoverTime(null)}
                  className="relative w-full h-3 bg-[#14121c]/90 hover:bg-[#14121c] rounded-xl border border-white/15 cursor-pointer overflow-hidden group select-none flex items-center shadow-inner"
                >
                  {/* Active Segment Region Highlight Block on Timeline */}
                  {activePlayingIndex !== null && segments[activePlayingIndex] && duration > 0 && (
                    <div
                      className="absolute top-0 bottom-0 bg-amber-500/40 border-x-2 border-amber-400 pointer-events-none z-10"
                      style={{
                        left: `${(segments[activePlayingIndex].start / duration) * 100}%`,
                        width: `${((segments[activePlayingIndex].end - segments[activePlayingIndex].start) / duration) * 100}%`
                      }}
                    />
                  )}

                  {/* Overall Song Playback Progress Fill */}
                  <div
                    className="absolute top-0 bottom-0 left-0 bg-gradient-to-r from-amber-500/40 via-amber-500/60 to-amber-400 pointer-events-none transition-all duration-75"
                    style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
                  />

                  {/* Playhead Needle Line */}
                  <div
                    className="absolute top-0 bottom-0 w-1.5 bg-amber-300 shadow-[0_0_12px_#f59e0b] pointer-events-none z-20"
                    style={{ left: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
                  />

                  {/* Hover Preview Marker & Tooltip */}
                  {hoverTime !== null && duration > 0 && (
                    <>
                      <div
                        className="absolute top-0 bottom-0 w-0.5 bg-white/90 pointer-events-none z-30"
                        style={{ left: `${(hoverTime / duration) * 100}%` }}
                      />
                      <div
                        className="absolute -top-7 px-2.5 py-0.5 bg-[#262230] text-amber-300 text-[10px] font-mono font-bold rounded-lg shadow-xl border border-amber-500/40 pointer-events-none z-40 transform -translate-x-1/2"
                        style={{ left: `${(hoverTime / duration) * 100}%` }}
                      >
                        {formatPrecisionTime(hoverTime)}
                      </div>
                    </>
                  )}
                </div>

                {/* High-Contrast Timeline Ruler & Time Labels (Cleanly positioned under track) */}
                <div className="flex items-center justify-between px-1 text-[11px] font-mono font-semibold select-none">
                  <span className="text-amber-300 font-bold bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">00:00.00</span>
                  <span className="text-zinc-200 font-medium">{formatPrecisionTime(duration * 0.25)}</span>
                  <span className="text-slate-200 font-bold bg-white/5 px-2.5 py-0.5 rounded-md border border-white/10">{formatPrecisionTime(duration * 0.5)}</span>
                  <span className="text-zinc-200 font-medium">{formatPrecisionTime(duration * 0.75)}</span>
                  <span className="text-amber-400 font-bold bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">{formatPrecisionTime(duration)}</span>
                </div>
              </div>

              {/* Smule Live Spacebar HUD Banner */}

            </div>

            {/* Scrollable List of Lyric Rows */}
            <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-5 sm:py-7 space-y-5 min-h-0 custom-scrollbar">
              {isLiveSyncMode && (
                <div className="p-3 sm:p-3.5 rounded-2xl bg-gradient-to-r from-pink-950/80 via-purple-950/80 to-slate-950/80 border border-pink-500/40 shadow-xl shadow-pink-500/10 space-y-2.5 animate-fade-in">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-pink-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-pink-500"></span>
                      </span>
                      <h4 className="text-xs font-black text-pink-300 tracking-wide uppercase font-mono">
                        Smule Canlı Space Senkronizasyonu
                      </h4>
                      <span className="text-[10px] font-bold text-pink-400/80 bg-pink-500/10 px-2 py-0.5 rounded-md border border-pink-500/20">
                        Satır #{liveSyncIndex + 1} / {segments.length}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleLiveSyncPrev}
                        disabled={liveSyncIndex === 0}
                        className="px-2.5 py-1 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-200 text-xs font-bold flex items-center gap-1 disabled:opacity-30 transition-all cursor-pointer"
                        title="Önceki satıra dön ve tekrar kaydet (Backspace)"
                      >
                        <Undo2 className="w-3.5 h-3.5" />
                        <span>Önceki satır (Backspace)</span>
                      </button>

                      <button onClick={undoAllLiveSync} disabled={!segments.length} title="Sözleri koruyarak tüm satır ve kelime zamanlamalarını temizle" className="rounded-xl border border-rose-400/25 bg-rose-400/10 px-3 py-1 text-xs font-bold text-rose-200 hover:bg-rose-400/20 disabled:opacity-30">Tüm zamanlamaları temizle</button>

                      <button
                        onClick={handleLiveSyncNext}
                        disabled={liveSyncIndex >= segments.length - 1}
                        className="px-2.5 py-1 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-200 text-xs font-bold flex items-center gap-1 disabled:opacity-30 transition-all cursor-pointer"
                        title="Bu satırı atla ve sonrakine geç (Tab / Sağ Ok)"
                      >
                        <span>Atla</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() => setIsLiveSyncMode(false)}
                        className="px-2.5 py-1 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-xs font-bold transition-all border border-rose-500/30 cursor-pointer"
                      >
                        Kapat (Esc)
                      </button>
                    </div>
                  </div>

                  <p className="text-xs text-pink-200">Ses parçası bağlanmış satırlar canlı senkronda değiştirilmez. Enter: canlı senkronu kapat ve oynatmayı durdur.</p>
                  <label className="block text-xs text-pink-200">Kayıt yöntemi
                    <StudioSelect aria-label="Canlı senkron kayıt yöntemi" value={liveGesture} className="ml-2 rounded bg-[#262230] p-2" onValueChange={value=>{
                      const mode=value as 'tap'|'hold';setLiveGesture(mode);setIsSpacePressed(false);
                      liveCaptureRef.current=mode==='tap'&&audioRef.current?{index:liveSyncIndex,start:audioRef.current.currentTime}:null;
                    }}><option value="tap">Satır bitince bas</option><option value="hold">Başlayınca tut, bitince bırak</option></StudioSelect>
                  </label>
                  {/* Real-time Instructions & Active Line Preview */}
                  <div className={cn(
                    "p-2.5 rounded-xl border transition-all flex items-center justify-between gap-4",
                    isSpacePressed
                      ? "bg-emerald-500/20 border-emerald-500/60 shadow-lg shadow-emerald-500/20"
                      : "bg-black/40 border-pink-500/30"
                  )}>
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-7 h-7 rounded-xl flex items-center justify-center font-mono font-black text-xs shrink-0 shadow-md",
                        isSpacePressed
                          ? "bg-emerald-400 text-slate-950 animate-pulse"
                          : "bg-pink-500/20 text-pink-300 border border-pink-500/40"
                      )}>
                        {isSpacePressed ? '🔴' : 'SPACE'}
                      </div>
                      <div>
                        <div className="text-[11px] font-bold text-zinc-400">
                          {isSpacePressed
                            ? 'SÖZ KAYDEDİLİYOR (Başlangıç: ' + formatPrecisionTime(spacePressStartTime || currentTime) + ') -> BİTTİĞİNDE SPACE TUŞUNU BIRAKIN!'
                            : (liveGesture==='tap'?'SATIR BİTİNCE SPACE’E BASIN. İLK BAŞLANGIÇ İÇİN ÖNCE OYNATICIYI KONUMLANDIRIN.':'SÖZ BAŞLADIĞINDA SPACE’E BASILI TUTUN, BİTİNCE BIRAKIN:')}
                        </div>
                        <div className="text-sm font-black text-white mt-0.5">
                          &quot;{currentSyncSegment ? currentSyncSegment.text : 'Söz Kalmadı'}&quot;
                        </div>
                      </div>
                    </div>

                    <div className="shrink-0 text-right font-mono text-xs">
                      {isSpacePressed ? (
                        <span className="text-emerald-300 font-black text-sm animate-pulse">
                          Kaydediliyor... ⏺️
                        </span>
                      ) : (
                        <span className="text-pink-300 font-bold">
                          Basılmayı Bekliyor ⏳
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
              {loadingLyrics ? (
                <div className="h-64 flex flex-col items-center justify-center gap-3 text-zinc-400">
                  <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
                  <p className="text-sm font-bold">Whisper AI vokalden şarkı sözlerini çıkarıyor...</p>
                </div>
              ) : segments.length === 0 ? (
                <div className="h-64 flex flex-col items-center justify-center gap-3 text-zinc-400 text-center">
                  <Mic2 className="w-10 h-10 stroke-1 text-amber-400" />
                  <p className="text-sm font-semibold">Henüz şarkı sözü eklenmedi.</p>
                  <button
                    onClick={() => handleAddSegment()}
                    className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs flex items-center gap-2 cursor-pointer"
                  >
                    <Plus className="w-4 h-4" />
                    <span>İlk Satırı Ekle</span>
                  </button>
                </div>
              ) : (
              segments.map((seg, idx) => {
                const nextSeg = segments[idx + 1];
                const isSinging = currentTime >= seg.start && currentTime <= seg.end;
                const isLingering = currentTime > seg.end && (nextSeg ? currentTime < nextSeg.start : currentTime <= seg.end + 2.5);
                const isRowActive = isSinging || isLingering;
                const isLoopingThis = loopLineIndex === idx;
                const isLiveTarget = isLiveSyncMode && liveSyncIndex === idx;
                const hasSustain = (seg.end - seg.start) >= 2.5;

                return (
                  <React.Fragment key={idx}>
                    {/* Breath / Es Pause Indicator between lines */}
                    {idx > 0 && segments[idx - 1] && (seg.start - segments[idx - 1].end) >= 1.5 && (
                      <div className="flex items-center justify-center gap-2 py-1 my-0.5 select-none">
                        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-emerald-500/20 to-transparent" />
                        <span className="text-[10px] font-mono font-bold text-emerald-400/90 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded-full flex items-center gap-1.5 shadow-sm">
                          <span>Ara</span>
                          <span className="text-emerald-300 font-black">{(seg.start - segments[idx - 1].end).toFixed(1)}s</span>

                        </span>
                        <div className="h-px flex-1 bg-gradient-to-r from-transparent via-emerald-500/20 to-transparent" />
                      </div>
                    )}

                    <div
                      ref={(el) => { rowRefs.current[idx] = el; }}
                      onClick={() => {
                        if (isLiveSyncMode) {
                          resumeLiveSyncFromRow(idx);
                        } else {
                          setLiveSyncIndex(idx);
                          const range = rowPlaybackRange(seg);
                          if(range.end > range.start)playLine(idx);
                        }
                      }}
                      className={cn(
                        "relative p-5 sm:p-6 rounded-2xl border transition-colors duration-200 group overflow-hidden cursor-pointer",
                        loadingLyrics && "pointer-events-none opacity-50",
                        isLiveTarget
                          ? isSpacePressed
                            ? "bg-emerald-500/15 border-emerald-400 shadow-xl shadow-emerald-500/20 ring-2 ring-emerald-400/50"
                            : "bg-pink-500/10 border-pink-400 shadow-xl shadow-pink-500/20 ring-2 ring-pink-400/40"
                          : isSinging
                          ? "bg-[#211e17] border-amber-400/40"
                          : isLingering
                          ? "bg-[#262230]/90 border-amber-500/30"
                          : activePlayingIndex === idx
                          ? "bg-[#14121c]/90 border-amber-500/40"
                          : "bg-[#262230] border-white/[0.07] hover:border-white/20"
                      )}
                    >
                      <div className="mb-3 flex items-center justify-between gap-3 text-xs text-zinc-400" onClick={e => e.stopPropagation()}>
                        <button type="button" className="rounded-lg border border-violet-300/25 px-3 py-1 text-violet-200" onClick={()=>toggleRowLock(idx)}>{seg.locked?'Kilitli · Kilidi aç':'Satırı kilitle'}</button>
                        <button type="button" className="font-mono text-left hover:text-indigo-200" onClick={() => isLiveSyncMode ? resumeLiveSyncFromRow(idx) : (setLiveSyncIndex(idx), seg.end > seg.start && playLine(idx))}>{String(idx + 1).padStart(2, '0')} <span className="ml-2">{seg.start === 0 && seg.end === 0 ? 'Zamanlama bekliyor' : formatPrecisionTime(seg.start)}</span></button>
                        <button type="button" onClick={() => resumeLiveSyncFromRow(idx)} disabled={loadingLyrics} className="ml-auto rounded-lg border border-pink-400/25 bg-pink-400/10 px-3 py-2 text-xs font-semibold text-pink-200 hover:bg-pink-400/20 disabled:opacity-40">Buradan canlı senkrona devam et</button>
                        {activeTab === 'lyrics' && getSegmentWords(seg).some(w => w.needs_review || w.timing_source === 'estimated') && <button onClick={() => {setExpandedWordRow(idx); setSelectedWordIndex(Math.max(0,getSegmentWords(seg).findIndex(w => w.needs_review || w.timing_source === 'estimated')));}} className="rounded-full border border-amber-400/20 bg-amber-400/5 px-2 py-1 text-xs text-amber-200">Kontrol gerekli</button>}
                      </div>
                      {activeTab === 'lyrics' && <div className="relative z-10 flex flex-wrap gap-x-2.5 gap-y-2 mb-5" onClick={e => e.stopPropagation()}>
                        {getSegmentWords(seg).map((w, wi) => (
                          <button key={wi} type="button" onClick={() => {if(isLiveSyncMode){resumeLiveSyncFromRow(idx);return;}setExpandedWordRow(idx); setSelectedWordIndex(wi); void playWord(idx, wi);}} title={`${w.start.toFixed(3)}–${w.end.toFixed(3)} s${w.needs_review ? ' · Zamanlama kontrol edilmeli' : ''}`}
                            className={cn('inline-flex items-baseline rounded-sm text-left text-xl sm:text-2xl leading-relaxed font-semibold text-zinc-200', expandedWordRow === idx && selectedWordIndex === wi && 'underline decoration-amber-400/60 underline-offset-8')} disabled={loadingLyrics}>
                            <span className="relative inline-block whitespace-pre">
                              <span>{w.word}</span>
                              <span aria-hidden className="pointer-events-none absolute inset-0 text-amber-400" style={{ clipPath: `inset(0 ${100 - wordFillWithNeighbors(w, currentTime, seg.words?.[wi - 1] ?? segments[idx - 1]?.words?.at(-1), seg.words?.[wi + 1] ?? nextSeg?.words?.[0]) * 100}% 0 0)` }}>{w.word}</span>
                            </span>
                          </button>
                        ))}
                      </div>}
                      <div className="relative z-10 flex flex-wrap items-center gap-3">
                        {/* Play Line Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            playRow(idx);
                          }}
                          className={cn(
                            'w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-transform active:scale-90 shadow-md',
                            (activePlayingIndex === idx || activePlayingWord?.segIdx === idx) && isPlaying
                              ? 'bg-amber-500 text-slate-950 shadow-amber-500/30'
                              : 'bg-white/5 hover:bg-amber-500/20 hover:text-amber-300 text-zinc-200'
                          )}
                          title="Satırın tamamını dinle"
                        >
                          {(activePlayingIndex === idx || activePlayingWord?.segIdx === idx) && isPlaying ? (
                            <Pause className="w-4 h-4 fill-current" />
                          ) : (
                            <Play className="w-4 h-4 fill-current ml-0.5" />
                          )}
                        </button>

                        {activeTab === 'lyrics' && expandedWordRow === idx && (
                          <button type="button" onClick={e => { e.stopPropagation(); playLine(idx); }}
                            className="text-xs text-zinc-400 hover:text-amber-300 px-2 py-2">
                            Satırın tamamını dinle
                          </button>
                        )}

                        {/* Loop Line Toggle */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleLoopLine(idx);
                          }}
                          className={cn(
                            'p-2 rounded-xl text-xs font-bold shrink-0 transition-all active:scale-90',
                            isLoopingThis
                              ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/30'
                              : 'bg-white/5 hover:bg-white/10 text-zinc-400'
                          )}
                          title={isLoopingThis ? 'Döngüyü Kapat' : 'Bu satırı sürekli tekrarla (İnce ayar için)'}
                        >
                          <Repeat className="w-3.5 h-3.5" />
                        </button>

                        {/* Precision Timing Inputs & Steppers */}
                        {activeTab === 'lyrics' && expandedWordRow === idx && showAdvancedTools && <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
                          {/* Start Timing Box */}
                          <div className="space-y-1">
                            <div className="flex items-center justify-between gap-1">
                              <span className="text-[9px] font-mono text-zinc-400 uppercase font-bold">Başlangıç</span>
                              <button
                                onClick={() => setPlayheadToSegment(idx, 'start')}
                                title="O an çalan süreyi bu satırın başlangıcı yap"
                                className="text-[9px] text-amber-400 hover:text-amber-300 font-bold underline cursor-pointer"
                              >
                                ⏱️ Şu Anı Al
                              </button>
                            </div>
                            <div className="flex items-center gap-0.5 bg-[#262230] rounded-lg p-0.5 border border-white/10 focus-within:border-amber-500 shadow-inner">
                              <button
                                onClick={() => stepSegmentTime(idx, 'start', -0.1)}
                                title="100ms geriye al"
                                className="px-1.5 py-0.5 text-[10px] font-mono text-zinc-400 hover:text-amber-400 hover:bg-white/5 rounded active:scale-95"
                              >
                                -0.1
                              </button>
                              <input
                                type="number"
                                step="0.001"
                                placeholder="—" value={seg.start === 0 && seg.end === 0 ? '' : Number(seg.start.toFixed(3))}
                                onChange={(e) => handleSegmentChange(idx, 'start', parseFloat(e.target.value) || 0)}
                                className="w-24 py-2 bg-transparent text-sm font-mono font-bold text-amber-300 text-center focus:outline-none"
                              />
                              <button
                                onClick={() => stepSegmentTime(idx, 'start', 0.1)}
                                title="100ms ileriye al"
                                className="px-1.5 py-0.5 text-[10px] font-mono text-zinc-400 hover:text-amber-400 hover:bg-white/5 rounded active:scale-95"
                              >
                                +0.1
                              </button>
                            </div>
                          </div>

                          <span className="text-slate-600 self-end pb-2 font-bold">-</span>

                          {/* End Timing Box */}
                          <div className="space-y-1">
                            <div className="flex items-center justify-between gap-1">
                              <span className="text-[9px] font-mono text-zinc-400 uppercase font-bold">Bitiş</span>
                              <button
                                onClick={() => setPlayheadToSegment(idx, 'end')}
                                title="O an çalan süreyi bu satırın bitişi yap"
                                className="text-[9px] text-amber-400 hover:text-amber-300 font-bold underline cursor-pointer"
                              >
                                ⏱️ Şu Anı Al
                              </button>
                            </div>
                            <div className="flex items-center gap-0.5 bg-[#262230] rounded-lg p-0.5 border border-white/10 focus-within:border-amber-500 shadow-inner">
                              <button
                                onClick={() => stepSegmentTime(idx, 'end', -0.1)}
                                title="100ms geriye al"
                                className="px-1.5 py-0.5 text-[10px] font-mono text-zinc-400 hover:text-amber-400 hover:bg-white/5 rounded active:scale-95"
                              >
                                -0.1
                              </button>
                              <input
                                type="number"
                                step="0.001"
                                placeholder="—" value={seg.start === 0 && seg.end === 0 ? '' : Number(seg.end.toFixed(3))}
                                onChange={(e) => handleSegmentChange(idx, 'end', parseFloat(e.target.value) || 0)}
                                className="w-24 py-2 bg-transparent text-sm font-mono font-bold text-amber-300 text-center focus:outline-none"
                              />
                              <button
                                onClick={() => stepSegmentTime(idx, 'end', 0.1)}
                                title="100ms ileriye al"
                                className="px-1.5 py-0.5 text-[10px] font-mono text-zinc-400 hover:text-amber-400 hover:bg-white/5 rounded active:scale-95"
                              >
                                +0.1
                              </button>
                            </div>
                          </div>
                        </div>}

                        {/* Text Input & Sustain Indicator */}
                        <div className="flex flex-1 min-w-[min(100%,460px)] items-center gap-3" onClick={e => e.stopPropagation()}>
                          <label className="flex-1 min-w-0">
                            <span className="block mb-1.5 text-xs font-medium text-zinc-400">Satırı düzenle</span>
                          <input
                            type="text"
                            aria-label={`${idx + 1}. satırın sözlerini düzenle`}
                            disabled={seg.locked}
                            onFocus={()=>{rowTextBaseline.current[seg.id||String(idx)]=structuredClone(seg.words||[]);}}
                            onBlur={()=>{delete rowTextBaseline.current[seg.id||String(idx)];history.current.breakGroup();}}
                            value={seg.text}
                            onChange={(e) => updateLyricInput(e.currentTarget, text=>handleSegmentChange(idx, 'text', text))}
                            className={cn(
                              "w-full px-4 py-3.5 rounded-xl border text-base font-medium placeholder-slate-500 focus:outline-none focus:border-amber-500 transition-all",
                              isLiveTarget
                                ? "bg-[#262230] border-pink-400 text-pink-200 font-bold"
                                : isSinging
                                ? "bg-[#262230]/90 border-amber-500/50 text-amber-200"
                                : "bg-[#191621] border-white/[0.08] text-white"
                            )}
                            placeholder="Şarkı sözü satırı..."
                          />
                          </label>
                          {hasSustain && activeTab === 'lyrics' && (
                            <span
                              className="text-[10px] font-mono text-amber-400 bg-amber-500/15 border border-amber-500/30 px-2 py-1 rounded-lg font-bold shrink-0 flex items-center gap-1 shadow-sm"
                              title="Satırın görünme süresi; kelime süreleri ayrı olarak korunur."
                            >
                              <span>⏱️ {(seg.end - seg.start).toFixed(1)}s</span>
                              <span className="text-amber-300 font-black">...</span>
                            </span>
                          )}
                        </div>

                        {activeTab === 'lyrics' && <button type="button" disabled={loadingLyrics} onClick={e=>{
                          e.stopPropagation(); stopWordPreview(); audioRef.current?.pause(); setIsPlaying(false);
                          if(seg.locked){onNotify('warning','Önce satır kilidini aç');return;}setPassageRow({index:idx,original:structuredClone(seg)});
                        }} className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-medium text-zinc-200 hover:bg-white/[0.08]">Ses parçalarını bağla</button>}
                        {/* Row Actions & Word-by-Word Button */}
                        <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-center" onClick={(e) => e.stopPropagation()}>
                          <button
                            disabled={seg.locked}
                            onClick={() => {setActiveTab('lyrics'); setSelectedWordIndex(0); setExpandedWordRow(expandedWordRow === idx ? null : idx);}}
                            className={cn(
                              "px-4 py-3 rounded-xl text-sm font-medium flex items-center gap-2 transition-all cursor-pointer shrink-0 border",
                              expandedWordRow === idx
                                ? "bg-amber-500/20 border-amber-500/50 text-amber-300 shadow-md shadow-amber-500/10"
                                : "bg-white/5 hover:bg-amber-500/10 hover:border-amber-500/30 text-zinc-200 hover:text-amber-200 border-white/10"
                            )}
                            title="Kelimeleri tek tek milisaniyelik sürelerle düzenleyin"
                          >
                            <Type className="w-3.5 h-3.5 text-amber-400" />
                            <span>{expandedWordRow === idx && activeTab === 'lyrics' ? 'Ayarları kapat' : 'Zaman ayarı'}</span>
                            <ChevronDown className={cn("w-3 h-3 opacity-70 transition-transform duration-200", expandedWordRow === idx && "rotate-180")} />
                          </button>

                          <button
                            onClick={() => handleAddSegment(idx)}
                            className="p-2 rounded-xl bg-white/[0.03] hover:bg-white/10 text-zinc-400 hover:text-white transition-colors cursor-pointer"
                            title="Altına Yeni Satır Ekle"
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </button>
                          <button
                            disabled={seg.locked}
                            onClick={() => handleDeleteSegment(idx)}
                            className="p-2 rounded-xl bg-white/[0.03] hover:bg-rose-500/20 text-zinc-400 hover:text-rose-400 transition-colors cursor-pointer"
                            title="Satırı Sil"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {/* Expandable Word-Level Timing Editor Tray */}
                      {activeTab === 'lyrics' && expandedWordRow === idx && (
                        <div className="relative z-10 mt-3 pt-3 border-t border-white/10 space-y-3 animate-in fade-in" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-between flex-wrap gap-2 text-xs bg-[#262230]/60 p-2.5 rounded-xl border border-white/5">
                            <div className="flex items-center gap-2 text-slate-200 font-bold">
                              <Sparkles className="w-4 h-4 text-amber-400" />
                              <span>Seçili kelimeyi ayarla</span>
                              <span className="text-[10px] font-mono text-zinc-400 bg-white/5 px-2 py-0.5 rounded border border-white/5">
                                {getSegmentWords(seg).length} Kelime
                              </span>
                            </div>
                            <div className={cn("flex items-center gap-1.5", !showAdvancedTools && "hidden")}>
                              <button
                                onClick={() => distributeWordsEvenly(idx)}
                                className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-200 hover:text-white text-[11px] font-bold border border-white/10 flex items-center gap-1 transition-all cursor-pointer"
                                title="Kelimeleri satır süresine eşit böl"
                              >
                                <span>⚖️ Taslak: Eşit Dağıt</span>
                              </button>
                              <button
                                onClick={() => distributeWordsBySyllables(idx)}
                                className="px-2.5 py-1 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 hover:text-white text-[11px] font-bold border border-indigo-500/30 flex items-center gap-1 transition-all cursor-pointer"
                                title="Kelimeleri hece sayılarına göre akıllıca paylaştır"
                              >
                                <span>✨ Taslak: Heceye Göre</span>
                              </button>
                              <button
                                onClick={() => handleAddWord(idx)}
                                className="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 hover:text-white text-[11px] font-bold border border-emerald-500/30 flex items-center gap-1 transition-all cursor-pointer"
                                title="Satırın sonuna yeni kelime ekle"
                              >
                                <Plus className="w-3 h-3" />
                                <span>Kelime Ekle</span>
                              </button>
                            </div>
                          </div>

                          {/* Word Chips Grid */}
                          <div className="flex flex-wrap gap-2">{getSegmentWords(seg).map((word, wordIndex) => <button key={wordIndex} aria-pressed={selectedWordIndex === wordIndex} onClick={() => setSelectedWordIndex(wordIndex)} className={cn('rounded-lg border px-3 py-2 text-sm', selectedWordIndex === wordIndex ? 'border-amber-400/40 bg-amber-400/10 text-amber-200' : 'border-white/10 text-zinc-400')}>{word.word}</button>)}</div>
                          <div className="w-full max-w-2xl">
                            {getSegmentWords(seg).map((w, wIdx) => {
                              if (wIdx !== selectedWordIndex) return null;
                              const isWordSinging = isPlaying && currentTime >= w.start && currentTime < w.end
                                && (!activePlayingWord || (activePlayingWord.segIdx === idx && activePlayingWord.wordIdx === wIdx));
                              const isThisWordPlaying = activePlayingWord?.segIdx === idx && activePlayingWord?.wordIdx === wIdx && isPlaying;
                              return (
                                <div
                                  key={wIdx}
                                  onClick={(e) => { e.stopPropagation(); void playWord(idx, wIdx); }}
                                  className={cn(
                                    "p-2.5 rounded-xl border transition-all flex flex-col gap-2 shadow-sm cursor-pointer select-none",
                                    isWordSinging
                                      ? "bg-amber-500/25 border-amber-400 ring-2 ring-amber-400/60 shadow-lg shadow-amber-500/20"
                                      : "bg-[#262230]/90 border-white/10 hover:border-amber-500/40"
                                  )}
                                >
                                  {/* Word Header with Play, Text Input & Delete */}
                                  <div className="flex items-center justify-between gap-1.5" onClick={(e) => e.stopPropagation()}>
                                    <div className="flex items-center gap-1.5 flex-1 min-w-0">
                                      <span className="text-[10px] font-mono font-bold text-zinc-400 shrink-0">#{wIdx + 1}</span>
                                      <input
                                        type="text"
                                        value={w.word}
                                        onChange={(e) => updateLyricInput(e.currentTarget, text=>handleWordTextChange(idx, wIdx, text))}
                                        className={cn(
                                          "w-full bg-transparent px-1.5 py-0.5 rounded border border-transparent focus:border-amber-500/50 text-xs font-black truncate focus:outline-none focus:bg-[#14121c] font-outfit",
                                          isWordSinging ? "text-amber-200 underline decoration-amber-400" : "text-white"
                                        )}
                                      />
                                    </div>
                                    <div className="flex items-center gap-1 shrink-0">
                                      <button
                                        onClick={() => playWord(idx, wIdx)}
                                        className={cn(
                                          "p-1 rounded-lg transition-all active:scale-95 cursor-pointer",
                                          isThisWordPlaying
                                            ? "bg-amber-500 text-slate-950 shadow-md shadow-amber-500/30 ring-1 ring-amber-400"
                                            : "bg-white/5 hover:bg-amber-500/20 hover:text-amber-300 text-zinc-400"
                                        )}
                                        title={isThisWordPlaying ? "Kelimeyi Durdur" : "Sadece bu kelimeyi dinle"}
                                      >
                                        {isThisWordPlaying ? <Pause className="w-3 h-3 fill-current" /> : <Play className="w-3 h-3" />}
                                      </button>
                                      <button
                                        onClick={() => {handleDeleteWord(idx, wIdx); setSelectedWordIndex(Math.max(0, wIdx - 1));}}
                                        className="p-1 rounded-lg bg-white/5 hover:bg-rose-500/20 hover:text-rose-400 text-zinc-400 transition-all active:scale-95 cursor-pointer"
                                        title="Bu kelimeyi kaldır"
                                      >
                                        <Trash2 className="w-3 h-3" />
                                      </button>
                                    </div>
                                  </div>

                                  {/* Start & End Steppers for this Word */}
                                  <div className="grid grid-cols-2 gap-1.5 text-[10px] font-mono" onClick={(e) => e.stopPropagation()}>
                                    {/* Word Start */}
                                    <div className="space-y-0.5">
                                      <div className="flex items-center justify-between text-[9px] text-zinc-400 font-bold px-0.5">
                                        <span>Başla</span>
                                        <button
                                          onClick={() => setPlayheadToWord(idx, wIdx, 'start')}
                                          className="text-amber-400 hover:text-amber-300 underline font-bold cursor-pointer"
                                          title="O an çalan süreyi bu kelimenin başlangıcı yap"
                                        >
                                          ⏱️ Al
                                        </button>
                                      </div>
                                      <div className="flex items-center bg-[#14121c] rounded-lg border border-white/10 p-0.5 focus-within:border-amber-500 shadow-inner">
                                        <button
                                          onClick={() => stepWordTime(idx, wIdx, 'start', -0.05)}
                                          className="px-1 text-zinc-400 hover:text-amber-300 hover:bg-white/5 rounded active:scale-95"
                                        >
                                          -
                                        </button>
                                        <input
                                          type="number"
                                          step="0.001"
                                          placeholder="—" value={w.start === 0 && w.end === 0 ? '' : Number(w.start.toFixed(3))}
                                          onChange={(e) => handleWordTimeChange(idx, wIdx, 'start', parseFloat(e.target.value) || 0)}
                                          className="w-full bg-transparent py-2 text-center text-amber-300 font-semibold text-sm focus:outline-none"
                                        />
                                        <button
                                          onClick={() => stepWordTime(idx, wIdx, 'start', 0.05)}
                                          className="px-1 text-zinc-400 hover:text-amber-300 hover:bg-white/5 rounded active:scale-95"
                                        >
                                          +
                                        </button>
                                      </div>
                                    </div>

                                    {/* Word End */}
                                    <div className="space-y-0.5">
                                      <div className="flex items-center justify-between text-[9px] text-zinc-400 font-bold px-0.5">
                                        <span>Bitir</span>
                                        <button
                                          onClick={() => setPlayheadToWord(idx, wIdx, 'end')}
                                          className="text-amber-400 hover:text-amber-300 underline font-bold cursor-pointer"
                                          title="O an çalan süreyi bu kelimenin bitişi yap"
                                        >
                                          ⏱️ Al
                                        </button>
                                      </div>
                                      <div className="flex items-center bg-[#14121c] rounded-lg border border-white/10 p-0.5 focus-within:border-amber-500 shadow-inner">
                                        <button
                                          onClick={() => stepWordTime(idx, wIdx, 'end', -0.05)}
                                          className="px-1 text-zinc-400 hover:text-amber-300 hover:bg-white/5 rounded active:scale-95"
                                        >
                                          -
                                        </button>
                                        <input
                                          type="number"
                                          step="0.001"
                                          placeholder="—" value={w.start === 0 && w.end === 0 ? '' : Number(w.end.toFixed(3))}
                                          onChange={(e) => handleWordTimeChange(idx, wIdx, 'end', parseFloat(e.target.value) || 0)}
                                          className="w-full bg-transparent py-2 text-center text-amber-300 font-semibold text-sm focus:outline-none"
                                        />
                                        <button
                                          onClick={() => stepWordTime(idx, wIdx, 'end', 0.05)}
                                          className="px-1 text-zinc-400 hover:text-amber-300 hover:bg-white/5 rounded active:scale-95"
                                        >
                                          +
                                        </button>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  </React.Fragment>
                );
                })
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Video Customization & Render */}
        {activeTab === 'video' && (
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 min-h-0 custom-scrollbar">
            <KaraokeVideoPreview onPlay={()=>{audioRef.current?.pause();stopWordPreview();}} key={instStem} file={instStem} segments={segments} theme={theme} aspectRatio={aspectRatio} header={showHeader ? [headerPrefix.trim(),[title.trim(),artist.trim()].filter(Boolean).join(' - ')].filter(Boolean).join(' • ') : ''} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Aspect Ratio Picker */}
              <div className="p-4 rounded-2xl bg-[#14121c]/60 border border-white/10 space-y-3">
                <label className="text-xs font-bold text-zinc-200 flex items-center gap-2">
                  <Monitor className="w-4 h-4 text-amber-400" />
                  <span>Video Formatı / En Boy Oranı</span>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => setAspectRatio('16:9')}
                    className={cn(
                      'p-3 rounded-xl border text-left transition-all flex items-center gap-3',
                      aspectRatio === '16:9'
                        ? 'bg-amber-500/20 border-amber-500/50 text-white'
                        : 'bg-white/5 border-white/5 text-zinc-400 hover:text-white'
                    )}
                  >
                    <Monitor className="w-5 h-5 text-amber-400" />
                    <div>
                      <div className="text-xs font-black">16:9 (Yatay)</div>
                      <div className="text-[10px] text-zinc-400">YouTube Standart</div>
                    </div>
                  </button>

                  <button
                    onClick={() => setAspectRatio('9:16')}
                    className={cn(
                      'p-3 rounded-xl border text-left transition-all flex items-center gap-3',
                      aspectRatio === '9:16'
                        ? 'bg-amber-500/20 border-amber-500/50 text-white'
                        : 'bg-white/5 border-white/5 text-zinc-400 hover:text-white'
                    )}
                  >
                    <Smartphone className="w-5 h-5 text-amber-400" />
                    <div>
                      <div className="text-xs font-black">9:16 (Dikey)</div>
                      <div className="text-[10px] text-zinc-400">Shorts / Reels / TikTok</div>
                    </div>
                  </button>
                </div>
              </div>

              {/* Theme Color Picker */}
              <div className="p-4 rounded-2xl bg-[#14121c]/60 border border-white/10 space-y-3">
                <label className="text-xs font-bold text-zinc-200 flex items-center gap-2">
                  <Palette className="w-4 h-4 text-amber-400" />
                  <span>Görsel Tema & Renk Paleti</span>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: 'gold', name: 'Gold Studio', color: 'from-amber-500 to-amber-700' },
                    { id: 'neon', name: 'Neon Sky', color: 'from-cyan-500 to-blue-600' },
                    { id: 'cyberpunk', name: 'Cyberpunk', color: 'from-pink-500 to-purple-600' },
                    { id: 'emerald', name: 'Emerald Wave', color: 'from-emerald-500 to-teal-700' },
                  ].map((tItem) => (
                    <button
                      key={tItem.id}
                      onClick={() => setTheme(tItem.id as any)}
                      className={cn(
                        'p-2.5 rounded-xl border text-left transition-all flex items-center gap-2.5',
                        theme === tItem.id
                          ? 'bg-white/10 border-amber-500/50 text-white shadow-md'
                          : 'bg-white/5 border-white/5 text-zinc-400 hover:text-white'
                      )}
                    >
                      <div className={cn('w-4 h-4 rounded-full bg-gradient-to-r shrink-0', tItem.color)} />
                      <span className="text-xs font-bold truncate">{tItem.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Video Header & Watermark Banner Customizer */}
            <div className="p-4 rounded-2xl bg-[#14121c]/60 border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-zinc-200 flex items-center gap-2">
                  <Music className="w-4 h-4 text-amber-400" />
                  <span>Video Üst Başlığı & Filigran (Özelleştirilebilir)</span>
                </label>
                <button
                  type="button"
                  onClick={() => setShowHeader(!showHeader)}
                  className={cn(
                    "px-3 py-1 rounded-xl text-xs font-bold transition-all border",
                    showHeader
                      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                      : "bg-white/5 text-zinc-400 border-white/10"
                  )}
                >
                  {showHeader ? "✓ Başlık Açık" : "✕ Başlık Gizli"}
                </button>
              </div>

              {showHeader && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <span className="text-[10px] font-mono text-zinc-400 uppercase block mb-1 font-bold">1. Ön Başlık / Etiket</span>
                      <input
                        type="text"
                        value={headerPrefix}
                        onChange={(e) => setHeaderPrefix(e.target.value)}
                        className="w-full p-2.5 rounded-xl bg-[#262230] border border-white/10 text-xs font-bold text-white focus:outline-none focus:border-amber-500"
                        placeholder="Örn: Orjinal Karaoke"
                      />
                    </div>
                    <div>
                      <span className="text-[10px] font-mono text-zinc-400 uppercase block mb-1 font-bold">2. Şarkı Adı</span>
                      <input
                        type="text"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        className="w-full p-2.5 rounded-xl bg-[#262230] border border-white/10 text-xs font-bold text-white focus:outline-none focus:border-amber-500"
                        placeholder="Şarkı Adı..."
                      />
                    </div>
                    <div>
                      <span className="text-[10px] font-mono text-zinc-400 uppercase block mb-1 font-bold">3. Sanatçı Adı</span>
                      <input
                        type="text"
                        value={artist}
                        onChange={(e) => setArtist(e.target.value)}
                        className="w-full p-2.5 rounded-xl bg-[#262230] border border-white/10 text-xs font-bold text-white focus:outline-none focus:border-amber-500"
                        placeholder="Sanatçı..."
                      />
                    </div>
                  </div>

                  {/* Live Header Text Preview */}
                  <div className="p-3 rounded-xl bg-black/50 border border-white/10 flex items-center justify-between gap-2">
                    <span className="text-[10px] font-mono uppercase text-zinc-400 font-bold shrink-0">Ekranda Gözükecek Başlık:</span>
                    <span className="text-xs font-bold font-mono text-amber-300 truncate">
                      {headerPrefix.trim() ? `${headerPrefix.trim()} • ` : ''}
                      {title.trim() || 'Şarkı Adı'}
                      {artist.trim() ? ` - ${artist.trim()}` : ''}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Video Preview Player (when rendered) */}
            {videoUrl && (
              <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 space-y-3 animate-fade-in">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <span className="text-xs font-bold text-emerald-300">1080p Video Hazır!</span>
                  </div>
                  <a
                    href={videoUrl}
                    download={videoFilename}
                    className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-xs flex items-center gap-2 shadow-lg shadow-amber-500/20 active:scale-95 transition-all cursor-pointer"
                  >
                    <Download className="w-4 h-4" />
                    <span>Videoyu İndir (MP4)</span>
                  </a>
                </div>

                <div className="rounded-2xl overflow-hidden border border-white/10 bg-black aspect-video max-h-64 flex items-center justify-center">
                  <video src={videoUrl} controls className="w-full h-full object-contain" />
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'video' && renderErrors.length > 0 && <div role="alert" className="border-t border-amber-400/15 bg-amber-400/5 px-6 py-3 text-sm text-amber-200">Video oluşturmadan önce düzelt: {renderErrors[0]} <button className="ml-2 underline underline-offset-4" onClick={() => setActiveTab('lyrics')}>Senkrona dön</button></div>}
        {/* Modal Footer */}
        <div className="px-5 py-3 sm:px-8 shrink-0 border-t border-white/[0.06] bg-[#14121c]/60 flex items-center justify-between gap-3">
          <div className="text-xs text-zinc-400">
            <span className="font-semibold text-slate-200">{segments.length} satır</span>
            <button disabled={!history.current.past.length||isLiveSyncMode} onClick={()=>restoreEdit('undo')} className="ml-3 disabled:opacity-30">Geri al</button>
            <button disabled={!history.current.future.length||isLiveSyncMode} onClick={()=>restoreEdit('redo')} className="ml-3 disabled:opacity-30">İleri al</button>
            <button onClick={() => {flushPendingSave(); void saveToDatabase(segments, true).catch(() => {});}} className="ml-3 text-zinc-400 hover:text-slate-200" title={lastSavedTime ? `Son kayıt: ${lastSavedTime}` : 'Şimdi kaydet'}>{isSavingDb ? 'Kaydediliyor…' : lastSavedTime ? '✓ Kaydedildi' : 'Kaydet'}</button>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                if (audioRef.current) audioRef.current.pause();
                onClose();
              }}
              className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-200 text-xs font-bold transition-all"
            >
              Kapat
            </button>

            <button
              onClick={() => activeTab === 'verify' ? setActiveTab('lyrics') : activeTab === 'lyrics' ? setActiveTab('video') : void handleGenerateVideo()}
              disabled={rendering || loadingLyrics || segments.length === 0 || (activeTab === 'video' && renderErrors.length > 0)}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-xs flex items-center gap-2 shadow-lg shadow-amber-500/20 active:scale-95 transition-all disabled:opacity-50"
            >
              {rendering ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{renderStatusMsg || 'FFmpeg 1080p Render Ediliyor...'}</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>{activeTab === 'verify' ? 'Senkronu kontrol et' : activeTab === 'lyrics' ? 'Video tasarımına geç' : 'Videoyu oluştur · 1080p'}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {passageRow && <AudioPassageEditor key={`${vocalStem || instStem}:${passageRow.index}`} file={vocalStem || instStem} row={passageRow.index} segment={passageRow.original}
        onClose={()=>setPassageRow(null)} onApply={updated=>{
          if (JSON.stringify(segments[passageRow.index]) !== JSON.stringify(passageRow.original)) throw Error('Satır bu sırada değişti. Düzenleyiciyi yeniden açın; son değişiklikler korundu.');
          const linked=(updated.words || []).filter(w=>w.end>w.start);
          const earlier=segments.slice(0,passageRow.index).flatMap(s=>s.words || []).filter(w=>w.end>w.start);
          const later=segments.slice(passageRow.index+1).flatMap(s=>s.words || []).filter(w=>w.end>w.start);
          if(linked.some(w=>earlier.some(p=>p.end>w.start+1e-7)||later.some(p=>p.start<w.end-1e-7))) throw Error('Bir ses bağlantısı başka satırın zamanına taşıyor. Sıralamayı korumak için bağlantıyı düzeltin.');
          const next=segments.map((s,i)=>i===passageRow.index?updated:s);
          setSegments(next); triggerAutoSave(next,true); setPassageRow(null);
        }} />}
      {showReferenceModal && <LyricsReferenceModal key={vocalStem || instStem} sourceFile={vocalStem || instStem} duration={duration} segments={segments} onClose={() => setShowReferenceModal(false)} onApply={async (snapshot, edits) => {
        if (JSON.stringify(snapshot) !== JSON.stringify(segments)) throw new Error('Sözler değişti; pencereyi yeniden açıp karşılaştırın.');
        const requestId = ++lyricsRequestRef.current;
        setLoadingLyrics(true);
        stopWordPreview(); audioRef.current?.pause();
        try {
          flushPendingSave();
          await enqueueLyricsSave(() => Promise.resolve());
          const result = await api.referenceRequest('apply', {file_name: vocalStem || instStem, segments: snapshot, edits, language: selectedLyricsLang, model_name: whisperModel});
          if (requestId !== lyricsRequestRef.current) return;
          setSegments(result.segments);
          setLastSavedTime(new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}));
          onNotify('success', 'Sözler düzeltildi', 'Seçilen satırlar sesle hizalandı. Diğer satırların zamanları korundu.');
        } finally { if (requestId === lyricsRequestRef.current) setLoadingLyrics(false); }
      }}/>}
      {/* Paste Lyrics & Auto-Align Modal */}
      {showPasteModal && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-[#14121c]/80 backdrop-blur-md animate-in fade-in">
          <div className="bg-[#262230] border border-purple-500/30 rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <ClipboardPaste className="w-5 h-5 text-purple-400" />
                <h3 className="text-base font-bold font-outfit text-white">Söz Yapıştır & Otomatik Hizala</h3>
              </div>
              <button
                onClick={() => setShowPasteModal(false)}
                className="p-1.5 rounded-xl hover:bg-white/10 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-zinc-400 leading-relaxed">
              Kaydınıza uygun sözleri aşağıya yapıştırın. Metin vokalle hizalanır; belirsiz kelime sınırları kontrol için işaretlenir. Yalnızca bazı satırları düzeltmek için “Sözleri bul ve doğrula” seçeneğini kullanın.
            </p>

            <textarea
              value={pastedLyricsText}
              onChange={(e) => updateLyricInput(e.currentTarget, setPastedLyricsText)}
              placeholder={"Örnek:\nBir fırtına tuttu bizi deryaya kardı\nO bizim kavuşmalarımız a mahşere kaldı\n..."}
              rows={8}
              className="w-full bg-[#14121c]/90 border border-white/10 focus:border-purple-500 rounded-2xl p-3.5 text-xs text-slate-200 outline-none resize-none font-mono leading-relaxed placeholder:text-slate-600"
            />

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setShowPasteModal(false)}
                className="px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-zinc-200 text-xs font-bold transition-all cursor-pointer"
              >
                Vazgeç
              </button>
              <button
                type="button"
                disabled={!pastedLyricsText.trim() || isAligningPasted}
                onClick={async () => {
                  setIsAligningPasted(true);
                  try {
                    await fetchInitialLyrics(vocalStem || instStem, true, whisperModel, pastedLyricsText);
                    setShowPasteModal(false);
                    setPastedLyricsText('');
                    onNotify('info', 'Hizalama tamamlandı', 'Kelime sınırları ses üzerinden çıkarıldı. İşaretlenen zamanları kontrol edin.');
                  } catch (e: any) {
                    onNotify('error', 'Hizalama Hatası', e.message);
                  } finally {
                    setIsAligningPasted(false);
                  }
                }}
                className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold flex items-center gap-2 transition-all active:scale-95 shadow-lg shadow-purple-600/30 cursor-pointer disabled:opacity-50"
              >
                {isAligningPasted ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Hizalanıyor...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Otomatik Senkronla & Başlat</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>,
    document.body
  );
};
