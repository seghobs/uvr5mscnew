import type { TimedWord } from './karaoke-timing';

export function sampleRange(start: number, end: number, sampleRate: number, length: number): [number, number] {
  if (![start, end, sampleRate, length].every(Number.isFinite) || start < 0 || end <= start || sampleRate <= 0 || end * sampleRate > length + 1) {
    throw new Error('Kelime süresi ses dosyasıyla uyuşmuyor.');
  }
  const first = Math.ceil(start * sampleRate);
  const last = Math.min(length, Math.floor(end * sampleRate));
  if (last <= first) throw new Error('Kelime süresi çok kısa.');
  return [first, last];
}

export function checkWordInterval(word: TimedWord, previousEnd = 0, nextStart = Infinity) {
  // Listening is how uncertain boundaries can be checked; it does not certify
  // them. Rendering and colour fill retain their separate confidence checks.
  if (!Number.isFinite(word.start) || !Number.isFinite(word.end) || word.start < 0 || word.end <= word.start || word.start < previousEnd - 1e-7 || word.end > nextStart + 1e-7) {
    throw new Error('Bu kelimenin süresi geçersiz veya komşusuyla çakışıyor. Zaman aralığını düzeltin ya da yeniden hizalayın.');
  }
}

export class WordPlayer {
  private context?: AudioContext;
  private buffer?: AudioBuffer;
  private bufferUrl = '';
  private source?: AudioBufferSourceNode;
  private generation = 0;
  private startedAt = 0;
  private offset = 0;
  private end = 0;
  private abort?: AbortController;
  private loading?: Promise<AudioBuffer>;
  private loadingUrl = '';
  private finishTimer?: ReturnType<typeof setTimeout>;

  private outputTime() {
    if (!this.context) return 0;
    const timestamp = this.context.getOutputTimestamp?.();
    if (timestamp && timestamp.contextTime > 0) return timestamp.contextTime;
    return Math.max(0, this.context.currentTime - (this.context.baseLatency || 0) - (this.context.outputLatency || 0));
  }

  get playing() { return !!this.source; }
  get currentTime() {
    return this.context ? Math.min(this.end, this.offset + Math.max(0, this.outputTime() - this.startedAt)) : this.offset;
  }

  stop() {
    this.generation++;
    if (this.finishTimer) clearTimeout(this.finishTimer);
    if (this.source) {
      this.source.onended = null;
      this.source.stop();
      this.source.disconnect();
      this.source = undefined;
    }
  }

  async prepare(url: string): Promise<AudioBuffer> {
    this.context ??= new AudioContext();
    if (this.buffer && this.bufferUrl === url) return this.buffer;
    if (this.loading && this.loadingUrl === url) return this.loading;
    this.abort?.abort();
    const abort = new AbortController();
    this.abort = abort;
    this.loadingUrl = url;
    const context = this.context;
    const loading = (async () => {
      const response = await fetch(url, { signal: abort.signal });
      if (!response.ok) throw new Error('Vokal ses dosyası yüklenemedi.');
      const buffer = await context.decodeAudioData(await response.arrayBuffer());
      if (abort.signal.aborted) throw new DOMException('Aborted', 'AbortError');
      this.buffer = buffer;
      this.bufferUrl = url;
      return buffer;
    })();
    this.loading = loading;
    try { return await loading; }
    finally { if (this.loading === loading) this.loading = undefined; }
  }

  async play(url: string, start: number, end: number, onEnded: () => void): Promise<boolean> {
    this.stop();
    const generation = this.generation;
    this.context ??= new AudioContext();
    await this.context.resume();
    if (generation !== this.generation) return false;
    const buffer = await this.prepare(url);
    if (generation !== this.generation) return false;
    const [first, last] = sampleRange(start, end, buffer.sampleRate, buffer.length);
    // Copy only this word: even a delayed main thread cannot play its neighbour.
    const clip = this.context.createBuffer(buffer.numberOfChannels, last - first, buffer.sampleRate);
    for (let channel = 0; channel < clip.numberOfChannels; channel++) {
      clip.copyToChannel(buffer.getChannelData(channel).subarray(first, last), channel);
    }
    const source = this.context.createBufferSource();
    source.buffer = clip;
    source.connect(this.context.destination);
    this.offset = first / buffer.sampleRate;
    this.end = last / buffer.sampleRate;
    this.startedAt = this.context.currentTime;
    this.source = source;
    source.onended = () => {
      source.disconnect();
      // Processing completion can precede speaker output. Do not fill the last
      // pixels until the hardware output clock reaches the end of the word.
      const drained = () => {
        if (generation !== this.generation) return;
        if (this.outputTime() < this.startedAt + clip.duration) {
          this.finishTimer = setTimeout(drained, 8);
          return;
        }
        this.source = undefined;
        onEnded();
      };
      drained();
    };
    source.start();
    return true;
  }

  dispose() {
    this.stop();
    this.abort?.abort();
    this.buffer = undefined;
    void this.context?.close();
    this.context = undefined;
  }
}
