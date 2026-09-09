const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../frontend/node_modules/typescript');
function load(file, extras = {}) {
  const ctx = { exports: {}, require, console, Promise, AbortController, DOMException, setTimeout, clearTimeout, ...extras };
  vm.createContext(ctx);
  vm.runInContext(ts.transpile(fs.readFileSync(file, 'utf8'), { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }), ctx);
  return ctx.exports;
}

async function main() {
  const timing = load('frontend/src/lib/karaoke-timing.ts');
  const tinyOverlap = [
    {text:'DUR',start:85,end:91.6,words:[{word:'DUR',start:85,end:91.6,needs_review:true}]},
    {text:'AY',start:91.59997732426304,end:92,words:[{word:'AY',start:91.59997732426304,end:92}]}
  ];
  const repaired = timing.repairTiming(tinyOverlap);
  assert.equal(repaired[0].words[0].end,tinyOverlap[1].words[0].start);
  assert.equal(tinyOverlap[0].words[0].end,91.6);
  assert.equal(repaired[0].words[0].needs_review,true);
  assert.equal(timing.timingIssues(repaired,false).length,0);
  assert.equal(JSON.stringify(timing.repairTiming(repaired)),JSON.stringify(repaired));
  tinyOverlap[1].words[0].start=91.5;
  assert.equal(timing.repairTiming(tinyOverlap)[0].words[0].end,91.6);
  assert.ok(timing.timingIssues(timing.repairTiming(tinyOverlap),false).length);
  const word = { word: 'örnek', start: 1.25, end: 1.75 };
  assert.equal(timing.wordFill(word, 1.249999), 0);
  assert.equal(timing.wordFill(word, 1.25), 0);
  assert.equal(timing.wordFill(word, 1.5), .5);
  assert.equal(timing.wordFill(word, 1.75), 1);
  assert.equal(timing.wordFill({...word, needs_review: true}, 1.5), .5);
  assert.equal(timing.wordFill({...word, timing_source:'estimated'}, 1.5), .5);
  assert.equal(timing.wordFill({...word, needs_review:true}, 1.249999), 0);
  assert.equal(timing.wordFill(word,1.5,1.3),0);
  assert.equal(timing.wordFill(word,1.5,0,1.6),0);
  const uncertain = {word:'İnadını', start:14.868256658595644, end:15.588692493946734, needs_review:true};
  assert.ok(Math.abs(timing.wordFill(uncertain,(uncertain.start+uncertain.end)/2)-.5)<1e-10);
  assert.ok(timing.timingIssues([{start:uncertain.start,end:uncertain.end,text:'İnadını',words:[uncertain]}]).length);
  assert.equal(timing.timingIssues([{start:uncertain.start,end:uncertain.end,text:'İnadını',words:[uncertain]}],false).length,0);
  assert.ok(timing.timingIssues([{start:uncertain.start,end:uncertain.end,text:'İnadını',words:[{...uncertain,end:uncertain.start}]}],false).length);
  const segments = [{ start: 1, end: 2, text: 'örnek', words: [word] }];
  assert.equal(timing.uppercaseLyric('i ı içe ışık dünya şişe'), 'İ I İÇE IŞIK DÜNYA ŞİŞE');
  const capitalized = timing.uppercaseLyrics(segments);
  assert.equal(capitalized[0].text,'ÖRNEK');
  assert.equal(capitalized[0].words[0].word,'ÖRNEK');
  assert.equal(capitalized[0].words[0].start,word.start);
  assert.equal(capitalized[0].words[0].end,word.end);
  assert.equal(capitalized[0].words[0].needs_review,word.needs_review);
  assert.equal(segments[0].text,'örnek');
  assert.equal(JSON.stringify(timing.importProject(timing.serializeProject(segments))), JSON.stringify(segments));
  assert.equal(JSON.stringify(timing.preserveWords([word])), JSON.stringify([word]));
  const originalWords = [
    {word:'İnadını',start:1,end:2}, {word:'bırak',start:3,end:4}, {word:'beni',start:5,end:6}
  ];
  const corrected = timing.reconcileWords(originalWords,'İnadına bırak beni');
  assert.equal(corrected[0].word,'İnadına');
  assert.equal(corrected[0].start,1);
  assert.equal(corrected[0].end,2);
  assert.equal(corrected[0].needs_review,true);
  assert.equal(JSON.stringify(corrected.slice(1)),JSON.stringify(originalWords.slice(1)));
  const inserted = timing.reconcileWords(originalWords,'İnadını bırak da beni');
  assert.equal(inserted[2].word,'da');
  assert.equal(inserted[2].start,inserted[2].end);
  assert.equal(inserted[3].start,5);
  const removed = timing.reconcileWords(originalWords,'İnadını beni');
  assert.equal(removed[1].start,5);
  assert.equal(timing.reconcileWords(originalWords,'').length,0);
  assert.equal(originalWords[0].word,'İnadını');
  assert.equal(timing.timingIssues(segments).length, 0);
  assert.ok(timing.timingIssues([{...segments[0], text: 'başka metin'}]).length);
  let release;
  const writes = [];
  const first = timing.enqueueLyricsSave(() => new Promise(resolve => { release = () => { writes.push(1); resolve(); }; }));
  const second = timing.enqueueLyricsSave(async () => { writes.push(2); });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(writes, []); release(); await Promise.all([first, second]);
  assert.deepEqual(writes, [1, 2]);
  await timing.enqueueLyricsSave(async () => { throw Error('offline'); }).catch(() => {});
  await timing.enqueueLyricsSave(async () => writes.push(3));
  assert.deepEqual(writes, [1, 2, 3]);

  const sources = [];
  function buffer(channels, length, rate) {
    const data = Array.from({length: channels}, () => new Float32Array(length));
    return { numberOfChannels: channels, length, sampleRate: rate, duration: length / rate, getChannelData: c => data[c], copyToChannel: (input, c) => data[c].set(input) };
  }
  const input = buffer(2, 4000, 1000);
  for (let c = 0; c < 2; c++) input.getChannelData(c).forEach((_, i, a) => a[i] = i < 1250 ? -1 : i < 1750 ? .5 : 1);
  let context;
  class AudioContext {
    constructor() { context = this; }
    currentTime = 50; destination = {};
    resume() { return Promise.resolve(); }
    close() { return Promise.resolve(); }
    decodeAudioData() { return Promise.resolve(input); }
    createBuffer(...args) { return buffer(...args); }
    createBufferSource() { const s = { connect() {}, disconnect() {}, start() {}, stop() { s.stopped = true; } }; sources.push(s); return s; }
  }
  const {WordPlayer, sampleRange, checkWordInterval} = load('frontend/src/lib/word-player.ts', { AudioContext, fetch: async () => ({ok: true, arrayBuffer: async () => new ArrayBuffer(0)}) });
  assert.deepEqual(Array.from(sampleRange(1.2501, 1.7499, 1000, 4000)), [1251, 1749]);
  assert.throws(() => checkWordInterval(word, 0, 1.5));
  assert.doesNotThrow(() => checkWordInterval({...word, needs_review:true}));
  assert.doesNotThrow(() => checkWordInterval({...word, timing_source:'estimated'}));
  assert.equal(timing.wordFill({...word, needs_review:true},1.5),.5);
  const player = new WordPlayer();
  await player.prepare('/vocal');
  let ended = 0;
  await player.play('/vocal', word.start, word.end, () => ended++);
  assert.equal(sources[0].buffer.length, 500);
  for (let c = 0; c < 2; c++) assert.ok(sources[0].buffer.getChannelData(c).every(x => x === .5));
  // No next-word samples exist in the clip, even if onended is delayed.
  await player.play('/vocal', 2, 2.2, () => ended++);
  assert.equal(sources[0].stopped, true);
  assert.equal(sources[0].onended, null);
  sources[1].onended(); assert.equal(ended, 0);
  context.currentTime = 51;
  await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(ended, 1);
  player.dispose();
  // Exercise the component's real click handler: a rejected word must silence
  // the previously playing word and the main audio, rather than let them leak.
  const component = ts.createSourceFile('modal.tsx', fs.readFileSync('frontend/src/components/KaraokeStudioModal.tsx', 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let handler;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(component) === 'playWord') handler = node.initializer.getText(component);
    ts.forEachChild(node, visit);
  }
  visit(component);
  assert.ok(handler);
  const handlers = {};
  function collect(node) {
    if (ts.isVariableDeclaration(node) && ['playRow','playLine','handleWordTimeChange'].includes(node.name.getText(component))) {
      handlers[node.name.getText(component)] = node.initializer.getText(component);
    }
    ts.forEachChild(node, collect);
  }
  collect(component);
  let rowPlayed, wordPlayed, editStopped = false, editPaused = false;
  const editContext = {
    activeTab:'lyrics', expandedWordRow:0, selectedWordIndex:1,
    segments:[{start:4.777,end:47,text:'SÖYLE YAĞMUR',words:[
      {word:'SÖYLE',start:4.777,end:5}, {word:'YAĞMUR',start:5,end:46.241}]}],
    getSegmentWords:seg=>seg.words,
    playWord:(...args)=>{wordPlayed=args;}, playLine:index=>{rowPlayed=index;},
    stopWordPreview:()=>{editStopped=true;},
    audioRef:{current:{currentTime:0,pause:()=>{editPaused=true;}}},
    wordPreviewEndRef:{current:5},linePreviewEndRef:{current:47},
    setActivePlayingIndex:()=>{},setIsPlaying:()=>{},setCurrentTime:()=>{},triggerAutoSave:()=>{},
  };
  editContext.setSegments = update => {editContext.segments=update(editContext.segments);};
  vm.createContext(editContext);
  for (const [name, body] of Object.entries(handlers)) {
    if (name === 'playLine') continue;
    vm.runInContext(ts.transpile(`globalThis.${name} = ${body}`,{target:ts.ScriptTarget.ES2020}),editContext);
  }
  editContext.handleWordTimeChange(0,1,'start',44.610);
  assert.equal(editStopped,true);
  assert.equal(editPaused,true);
  assert.equal(editContext.audioRef.current.currentTime,44.610);
  assert.equal(editContext.segments[0].words[1].start,44.610);
  assert.equal(editContext.segments[0].start,4.777);
  editContext.playRow(0);
  assert.deepEqual(wordPlayed,[0,1]);
  assert.equal(rowPlayed,undefined);
  editContext.expandedWordRow=null;
  editContext.playRow(0);
  assert.equal(rowPlayed,0);
  // Real stale-envelope case: the row still starts at 4.777, all words moved
  // to 44s, and the second word overlaps the first. Whole-row audition must
  // never seek back to the stale intro.
  const stale = {start:4.777,end:49.283,text:'SÖYLE YAĞMUR',words:[
    {word:'SÖYLE',start:44.777,end:45.545}, {word:'YAĞMUR',start:44.610,end:46.241}]};
  assert.equal(timing.rowPlaybackRange(stale).start,44.610);
  assert.equal(timing.rowPlaybackRange(stale).end,46.241);
  assert.equal(timing.rowPlaybackRange({start:3,end:4,text:'x'}).start,3);
  const lineContext = {
    segments:[stale], stopWordPreview:()=>{},rowPlaybackRange:timing.rowPlaybackRange,
    audioRef:{current:{currentTime:0,play:()=>Promise.resolve(),pause:()=>{}}},
    activePlayingIndex:null,isPlaying:false,loopLineIndex:null,
    wordPreviewEndRef:{current:null},linePreviewEndRef:{current:null},
    setActivePlayingWord:()=>{},setActivePlayingIndex:()=>{},setCurrentTime:()=>{},
  };
  vm.createContext(lineContext);
  vm.runInContext(ts.transpile(`globalThis.playLine = ${handlers.playLine}`,{target:ts.ScriptTarget.ES2020}),lineContext);
  lineContext.playLine(0);
  assert.equal(lineContext.audioRef.current.currentTime,44.610);
  assert.equal(lineContext.linePreviewEndRef.current,46.241);
  editContext.expandedWordRow=0;
  editContext.activeTab='verify';
  rowPlayed=undefined;
  editContext.playRow(0);
  assert.equal(rowPlayed,0);
  const clicked = {...word, end:word.start, needs_review: true};
  let previousPlaying = true, mainPlaying = true, warning = '';
  const clickContext = {
    loadingLyrics: false, segments: [{words:[clicked]}], activePlayingWord: {segIdx:0,wordIdx:1},
    wordPlayerRef: {current:{playing:true}},
    stopWordPreview: () => { previousPlaying = false; },
    audioRef: {current:{pause: () => {mainPlaying = false;}}},
    linePreviewEndRef:{current:2}, setActivePlayingIndex:()=>{}, setIsPlaying:()=>{},
    wordRequestRef:{current:0}, checkWordInterval,
    onNotify:(_kind,_title,message)=>{warning = message;},
  };
  vm.createContext(clickContext);
  vm.runInContext(ts.transpile(`globalThis.clickWord = ${handler}`, {target:ts.ScriptTarget.ES2020}),clickContext);
  await clickContext.clickWord(0,0);
  assert.equal(previousPlaying, false);
  assert.equal(mainPlaying, false);
  assert.ok(warning.includes('geçersiz'));
  // A valid but uncertain interval must reach the player without clearing its
  // review flag or certifying it for export.
  clicked.end = word.end;
  let previewed;
  clickContext.vocalStem = 'vocal.wav';
  clickContext.setCurrentTime = () => {};
  clickContext.setActivePlayingWord = () => {};
  clickContext.wordPlayerRef.current.play = async (url,start,end) => {previewed = [url,start,end]; return true;};
  await clickContext.clickWord(0,0);
  assert.deepEqual(previewed, ['/output/vocal.wav',word.start,word.end]);
  assert.equal(clicked.needs_review,true);
  clickContext.segments = [{words:[{...word,end:1.4},clicked]}];
  clickContext.activePlayingWord = null;
  warning='';
  await clickContext.clickWord(0,1);
  assert.deepEqual(previewed, ['/output/vocal.wav',word.start,word.end]);
  assert.ok(warning.includes('komşu kelime'));
  console.log('PASS: word boundaries, no early fill, lossless import/export, ordered saves, sample-isolated playback, rapid clicks');
}
main().catch(err => { console.error(err); process.exitCode = 1; });
