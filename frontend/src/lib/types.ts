export type TabId = 'roformer' | 'mdx23c' | 'mdxnet' | 'vrarch' | 'demucs' | 'library' | 'leaderboard' | 'batch';

export type Language = 'tr' | 'en';

export type AccentColor = 'indigo' | 'emerald' | 'rose' | 'amber' | 'violet';

export interface SeparationParams {
  ensemble_profile?: "studio_pro" | "atlas_studio";
  // Roformer / MDX23C
  segment_size?: number;
  override_segment_size?: boolean;
  overlap?: number;
  batch_size?: number;
  normalization_threshold?: number;
  amplification_threshold?: number;
  single_stem?: string;
  // MDX-Net specific
  hop_length?: number;
  denoise?: boolean;
  // VR Arch specific
  window_size?: number;
  aggression?: number;
  tta?: boolean;
  post_process?: boolean;
  post_process_threshold?: number;
  high_end_process?: boolean;
  // Demucs specific
  shifts?: number;
  segments_enabled?: boolean;
}

export interface EnsembleSlot {
  model_type: string;
  model_key: string;
}

export interface AvailableModels {
  [key: string]: string[];
}

export interface ModelStatus {
  cached: boolean;
  total_files: number;
  existing: string[];
}

export interface LibraryItem {
  settings?: {params: SeparationParams; model: string; tab: TabId; ensembleMode: boolean; ensembleSlots: EnsembleSlot[]; format: string};
  id: number;
  filename: string;
  stems: string[];
  timestamp: string;
  model_name?: string;
  ensemble_mode?: boolean;
  key?: string;
  bpm?: number;
  duration?: number;
}

export interface SearchResult {
  id?: string;
  title: string;
  url: string;
  duration?: string | number;
  thumbnail?: string;
  channel?: string;
}

export interface TaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message?: string;
  error?: string;
  results?: string[];
  stems?: string[];
}

export interface LeaderboardEntry {
  model: string;
  score: string;
  speed: string;
  type: string;
}

export interface BatchRequest {
  input_dir: string;
  output_dir?: string;
  model_type: string;
  model_key: string;
  out_format: string;
  params?: SeparationParams;
}

export interface AudioAnalysis {
  bpm: number;
  key: string;
  root_note: string;
  scale: string;
  camelot: string;
  duration?: number;
}

export interface LyricSegment {
  id?: string;
  locked?: boolean;
  start: number;
  end: number;
  text: string;
  words?: Array<{ word: string; start: number; end: number; probability?: number | null; timing_source?: 'aligned' | 'ctc' | 'manual' | 'estimated'; needs_review?: boolean }>;
}

export interface LyricsResponse {
  paste_report?: {mode:'line_by_line';total:number;aligned:number;pending:number[]} | null;
  timing_issues?: string[];
  status: string;
  cached?: boolean;
  is_edited?: boolean;
  updated_at?: string;
  segments: LyricSegment[];
  lrc_content: string;
  srt_content: string;
  lrc_file: string;
  srt_file: string;
}

export interface VisualizerResponse {
  status: string;
  video_file: string;
  download_url: string;
}

export interface KaraokeVideoResponse {
  status: string;
  video_file: string;
  download_url: string;
}

export interface RestoreAudioParams {
  file_name: string;
  denoise?: boolean;
  enhance_sr?: boolean;
  ddim_steps?: number;
  guidance_scale?: number;
}

export interface RestoreAudioResponse {
  status: string;
  output_file: string;
  download_url: string;
  stem_file?: string;
  message?: string;
}
