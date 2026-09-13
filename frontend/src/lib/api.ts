import { AvailableModels, ModelStatus, SeparationParams, TaskStatus, SearchResult, EnsembleSlot, LyricSegment, LyricsResponse, RestoreAudioParams, RestoreAudioResponse } from './types';

async function safeFetch(path: string, options?: RequestInit): Promise<Response> {
  const isBrowser = typeof window !== 'undefined';
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const canRetry = !options?.method || options.method === 'GET';

  try {
    const res = await fetch(cleanPath, options);
    if (res.ok) return res;

    // If proxy failed, retry directly against FastAPI backend port 8000
    if (isBrowser && canRetry && (res.status === 404 || res.status === 405 || res.status >= 500)) {
      const directUrl = `http://127.0.0.1:8000${cleanPath}`;
      const directRes = await fetch(directUrl, options).catch(() => null);
      if (directRes && directRes.ok) return directRes;
    }
    return res;
  } catch (err) {
    if (isBrowser && canRetry) {
      const directUrl = `http://127.0.0.1:8000${cleanPath}`;
      const directRes = await fetch(directUrl, options).catch(() => null);
      if (directRes && directRes.ok) return directRes;
    }
    throw err;
  }
}

export const api = {
  async transcribeAudioAI(fileName:string,onProgress:(message:string)=>void):Promise<{segments:LyricSegment[];review_required:boolean}>{
    const response=await safeFetch('/api/lyrics/ai-transcribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file_name:fileName})});
    const job=await response.json();if(!response.ok)throw Error(job.detail||'Gemini başlatılamadı.');
    for(let i=0;i<7200;i++){
      await new Promise(resolve=>setTimeout(resolve,1000));
      const response=await safeFetch(`/status/${encodeURIComponent(job.task_id)}`);
      if(!response.ok)throw Error('Gemini işlemi sorgulanamadı.');
      const data=await response.json();if(data.message)onProgress(data.message);
      if(data.status==='completed')return data.result;
      if(data.status==='failed')throw Error(data.error||'Gemini söz çıkaramadı.');
    }
    throw Error('İşlem sunucuda devam ediyor olabilir.');
  },
  async reviewLyricsAI(fileName:string,segments:LyricSegment[],onProgress:(message:string)=>void):Promise<LyricsResponse & {ai_report:{checked:number;changed:number;rejected:number}}>{
    const response=await safeFetch('/api/lyrics/ai-review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file_name:fileName,segments})});
    const job=await response.json();
    if(!response.ok)throw Error(job.detail||'AI incelemesi başlatılamadı.');
    for(let i=0;i<7200;i++){
      await new Promise(resolve=>setTimeout(resolve,1000));
      const status=await safeFetch(`/status/${encodeURIComponent(job.task_id)}`);
      if(!status.ok)throw Error('AI incelemesi sorgulanamadı.');
      const data=await status.json();
      if(data.message)onProgress(data.message);
      if(data.status==='completed')return data.result;
      if(data.status==='failed')throw Error(data.error||'AI incelemesi başarısız.');
    }
    throw Error('AI incelemesi sunucuda devam ediyor olabilir.');
  },
  async referenceRequest(path: 'search' | 'compare' | 'apply', body: unknown): Promise<any> {
    const res = await safeFetch(`/api/lyrics/reference/${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Söz doğrulama tamamlanamadı.');
    if (!data.task_id) return data;
    for (let i = 0; i < 7200; i++) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      const status = await safeFetch(`/status/${encodeURIComponent(data.task_id)}`);
      if (!status.ok) throw new Error('Hizalama durumu alınamadı.');
      const task = await status.json();
      if (task.status === 'completed') return task.result;
      if (task.status === 'failed') throw new Error(task.error || 'Düzeltme hizalanamadı.');
    }
    throw new Error('İşlem sunucuda devam ediyor olabilir.');
  },
  async getModels(): Promise<AvailableModels> {
    const res = await safeFetch('/models');
    if (!res.ok) throw new Error('Failed to fetch models');
    return res.json();
  },

  async getModelStatus(modelKey: string): Promise<ModelStatus> {
    const res = await safeFetch(`/model_status/${encodeURIComponent(modelKey)}`);
    if (!res.ok) throw new Error('Failed to fetch model status');
    return res.json();
  },

  async downloadModel(modelKey: string): Promise<{ task_id: string }> {
    const res = await safeFetch('/download_model', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_key: modelKey }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Failed to start model download');
    }
    return res.json();
  },

  async getFavorites(): Promise<string[]> {
    try {
      const res = await safeFetch('/api/favorites');
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data.favorites) ? data.favorites : [];
    } catch {
      return [];
    }
  },

  async toggleFavorite(modelName: string): Promise<{ status: string; favorites: string[] }> {
    const res = await safeFetch('/api/favorites/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_name: modelName }),
    });
    if (!res.ok) throw new Error('Failed to toggle favorite');
    return res.json();
  },

  async uploadAudio(file: File): Promise<{ filename: string; path: string }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await safeFetch('/upload', {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Upload failed');
    }
    const data = await res.json();
    return {
      filename: data.filename || file.name,
      path: data.path || data.file_path || '',
    };
  },

  async downloadFromUrl(url: string): Promise<{ filename: string; path: string; title: string }> {
    const res = await safeFetch('/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Download failed');
    }
    const data = await res.json();
    return {
      filename: data.filename || 'downloaded_audio',
      path: data.path || data.file_path || '',
      title: data.title || data.filename || 'Downloaded Audio',
    };
  },

  async search(query: string, maxResults: number = 20): Promise<SearchResult[]> {
    const res = await safeFetch(`/search?q=${encodeURIComponent(query)}&max_results=${maxResults}`);
    if (!res.ok) throw new Error('Search failed');
    const data = await res.json();
    return Array.isArray(data) ? data : (data.results || []);
  },

  async startSeparation(payload: {
    model_type: string;
    model_key: string;
    audio_path: string;
    out_format: string;
    params: SeparationParams;
  }): Promise<{ task_id: string }> {
    const res = await safeFetch('/separate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Separation request failed');
    }
    return res.json();
  },

  async startEnsemble(payload: {
    models: EnsembleSlot[];
    audio_path: string;
    out_format: string;
    params: SeparationParams;
  }): Promise<{ task_id: string }> {
    const res = await safeFetch('/ensemble', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Ensemble request failed');
    }
    return res.json();
  },

  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const res = await safeFetch(`/status/${encodeURIComponent(taskId)}`);
    if (!res.ok) throw new Error('Task status fetch failed');
    return res.json();
  },

  async modifyAudio(payload: {
    file_name: string;
    pitch_semitones: number;
    tempo_factor: number;
  }): Promise<{ status: string; filename: string; message?: string }> {
    const res = await safeFetch('/modify_audio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Modify audio failed');
    return res.json();
  },

  async remixAudio(payload: {
    vocal_file: string;
    inst_file: string;
    vocal_gain: number;
    inst_gain: number;
    pitch_shift: number;
    tempo_factor: number;
    out_format: string;
  }): Promise<{ filename: string; message: string }> {
    const res = await safeFetch('/remix', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Remix request failed');
    return res.json();
  },

  async getLeaderboard(filter: string): Promise<{ html: string }> {
    const res = await safeFetch(`/leaderboard?filter=${encodeURIComponent(filter)}`);
    if (!res.ok) throw new Error('Leaderboard fetch failed');
    return res.json();
  },

  async startBatch(payload: {
    input_dir: string;
    output_dir?: string;
    model_type: string;
    model_key: string;
    out_format: string;
    params?: SeparationParams;
  }): Promise<{ task_id: string }> {
    const res = await safeFetch('/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Batch separation request failed');
    }
    return res.json();
  },

  async analyzeAudio(fileName: string): Promise<{
    bpm: number;
    key: string;
    root_note: string;
    scale: string;
    camelot: string;
    duration?: number;
  }> {
    const res = await safeFetch('/analyze_audio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: fileName }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Audio analysis failed');
    }
    return res.json();
  },

  async transcribeLyrics(
    fileName: string,
    language: string = 'auto',
    force: boolean = false,
    modelName: string = 'large-v3',
    rawLyricsText?: string,
    onProgress?: (message:string)=>void
  ): Promise<LyricsResponse> {
    const isPaste=Boolean(rawLyricsText?.trim());
    const signal=isPaste?AbortSignal.timeout(90000):undefined;
    const res = await safeFetch(rawLyricsText?.trim()?'/api/lyrics/paste':'/transcribe_lyrics', {
      method: 'POST',
      signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_name: fileName,
        language,
        force,
        model_name: modelName,
        raw_lyrics_text: rawLyricsText,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Lyrics transcription failed');
    }
    const data = await res.json();
    if (!data.task_id) return data;
    for (let attempt = 0; attempt < (isPaste?90:7200); attempt++) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      const statusRes = await safeFetch(`/status/${encodeURIComponent(data.task_id)}`,{signal});
      if (!statusRes.ok) throw new Error('Hizalama görevi sorgulanamadı.');
      const task = await statusRes.json();
      if(task.message)onProgress?.(task.message);
      if (task.status === 'completed') return task.result;
      if (task.status === 'failed') throw new Error(task.error || 'Hizalama başarısız.');
    }
    throw new Error('Hizalama bekleme süresi doldu; görev sunucuda devam ediyor olabilir.');
  },

  async saveLyrics(
    fileName: string,
    segments: LyricSegment[],
    language: string = 'tr'
  ): Promise<LyricsResponse> {
    const res = await safeFetch('/save_lyrics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: fileName, language, segments }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Failed to save lyrics to database');
    }
    return res.json();
  },

  async getSavedLyrics(fileName: string): Promise<LyricsResponse> {
    const res = await safeFetch(`/lyrics/${encodeURIComponent(fileName)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'No saved lyrics found');
    }
    return res.json();
  },

  async quickClean(payload: {
    file_name: string;
    clean_type: 'dereverb' | 'debleed';
    out_format?: string;
  }): Promise<{ task_id: string }> {
    const res = await safeFetch('/quick_clean', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Quick clean request failed');
    }
    return res.json();
  },

  async generateVisualizer(payload: {
    file_name: string;
    aspect_ratio?: '9:16' | '16:9';
    theme?: 'neon' | 'gold' | 'cyberpunk';
    title?: string;
  }): Promise<{ status: string; video_file: string; download_url: string }> {
    const res = await safeFetch('/generate_visualizer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Visualizer generation failed');
    }
    return res.json();
  },

  async generateKaraokeVideo(
    payload: {
      inst_file: string;
      timing_file?: string;
      segments: Array<{ start: number; end: number; text: string; words?: any[] }>;
      title?: string;
      artist?: string;
      header_text?: string;
      show_header?: boolean;
      aspect_ratio?: '16:9' | '9:16';
      theme?: 'gold' | 'neon' | 'cyberpunk' | 'emerald';
    },
    onProgress?: (message: string, progress: number) => void
  ): Promise<{ status: string; video_file: string; download_url: string }> {
    const res = await safeFetch('/generate_karaoke_video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Karaoke video generation failed');
    }
    const data = await res.json();
    if (data.download_url) {
      return data;
    }

    if (data.task_id) {
      const taskId = data.task_id;
      const maxAttempts = 9000; // Up to two hours for long 60 fps renders.
      for (let i = 0; i < maxAttempts; i++) {
        await new Promise((r) => setTimeout(r, 800));
        const statusRes = await safeFetch(`/status/${taskId}`);
        if (statusRes.ok) {
          const taskData = await statusRes.json();
          if (onProgress && taskData.message) {
            onProgress(taskData.message, taskData.progress || 0);
          }
          if (taskData.status === 'completed') {
            return {
              status: 'success',
              video_file: taskData.video_file || '',
              download_url: taskData.download_url || `/output/${taskData.video_file}`,
            };
          }
          if (taskData.status === 'failed') {
            throw new Error(taskData.error || taskData.message || 'Video render failed');
          }
        }
      }
      throw new Error('Video render timed out');
    }

    return data;
  },

  async clearKaraokeData(): Promise<{
    status: string;
    message: string;
    deleted_lyrics_count: number;
    deleted_files_count: number;
  }> {
    const res = await safeFetch('/api/projects/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Karaoke verileri temizlenemedi');
    }
    return res.json();
  },

  async getWhisperStatus(): Promise<{
    model_name: string;
    key: string;
    installed: boolean;
    size_mb: number;
    models?: Array<{
      key: string;
      model_name: string;
      installed: boolean;
      size_mb: number;
      desc: string;
      recommended: boolean;
    }>;
  }> {
    const res = await safeFetch('/whisper_status');
    if (!res.ok) {
      return {
        model_name: 'Whisper Large-V3 (Full HQ)',
        key: 'large-v3',
        installed: false,
        size_mb: 0,
      };
    }
    return res.json();
  },

  async downloadWhisperModel(modelType: string = 'large-v3'): Promise<{ status: string; task_id: string }> {
    const res = await safeFetch('/download_whisper', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_type: modelType }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Whisper download failed');
    }
    return res.json();
  },

  async restoreAudio(
    params: RestoreAudioParams,
    onProgress?: (message: string, progress: number) => void
  ): Promise<RestoreAudioResponse> {
    const res = await safeFetch('/restore_audio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Restorasyon başlatılamadı');
    }
    const data = await res.json();
    if (!data.task_id) {
      return data;
    }

    const taskId = data.task_id;
    const maxAttempts = 600; // 10 minutes max
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise((r) => setTimeout(r, 1000));
      const statusRes = await safeFetch(`/status/${taskId}`);
      if (statusRes.ok) {
        const taskData = await statusRes.json();
        if (onProgress && taskData.message) {
          const p = typeof taskData.progress === 'number' ? Math.round(taskData.progress * 100) : 0;
          onProgress(taskData.message, p);
        }
        if (taskData.status === 'completed') {
          return {
            status: 'success',
            output_file: taskData.output_file || taskData.stem_file || '',
            download_url: taskData.download_url || `/output/${taskData.output_file}`,
            stem_file: taskData.stem_file || taskData.output_file,
            message: taskData.message,
          };
        }
        if (taskData.status === 'failed') {
          throw new Error(taskData.error || taskData.message || 'Restorasyon başarısız oldu');
        }
      }
    }
    throw new Error('Restorasyon işlemi zaman aşımına uğradı');
  },

  async clearMemory(): Promise<{ status: string; message: string; gpu?: { allocated_mb: number; reserved_mb: number; max_allocated_mb?: number; device_name?: string } }> {
    const res = await safeFetch('/clear_memory', { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Bellek temizlenemedi');
    }
    return res.json();
  },

  async shutdown(): Promise<{ status: string; message: string }> {
    const res = await safeFetch('/shutdown', { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || 'Shutdown failed');
    }
    return res.json();
  },
};
