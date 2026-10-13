const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ts=require('../frontend/node_modules/typescript');
const source=fs.readFileSync('frontend/src/components/KaraokeStudioModal.tsx','utf8');
const handler=source.slice(source.indexOf('  const clearSongLyrics=async()=>{'),source.indexOf('  const cancelAllTasks=async()=>{'));
assert(handler.includes('api.saveLyrics(file,[],selectedLyricsLang)'));
assert(!handler.includes('cancelAllTasks')&&!handler.includes('clearKaraokeData'));
assert(source.includes('aria-labelledby="clear-lyrics-title"'));
async function check(fail=false,switchSong=false){
  const saved=[],loaded=[],events=[];
  const storage=new Map([
    ['uvr-lyrics-draft:current.wav','old'],['uvr-history:current.wav','old'],
    ['uvr-passages-v3:current.wav:row','old'],['uvr-lyrics-draft:other.wav','keep'],
    ['uvr-passages-v3:other.wav:row','keep'],
  ]);
  const context={clearingLyrics:false,loadingLyrics:false,bulkBindingStatus:null,
    vocalStem:'current.wav',instStem:'instrumental.wav',selectedLyricsLang:'tr',lyricsRequestRef:{current:0},
    wordRequestRef:{current:0},liveCaptureRef:{current:{}},audioRef:{current:{pause(){}}},
    stopWordPreview(){},setClearingLyrics(){},setIsLiveSyncMode(){},setIsSpacePressed(){},
    flushPendingSave(){events.push('flush');},
    async enqueueLyricsSave(fn){events.push('queue');return fn();},
    api:{async saveLyrics(file,rows){saved.push({file,rows});if(fail)throw Error('save failed');if(switchSong)context.lyricsRequestRef.current++;}},
    projectStorage:{removeItem:k=>storage.delete(k),keys:()=>[...storage.keys()]},
    loadSegments:rows=>loaded.push(rows),setLiveLyricsSegments(){},setBulkBindingProblems(){},
    setPassageRow(){},setLastSavedTime(){},setShowClearLyrics(){},onNotify(){},Date,
  };
  vm.createContext(context);
  vm.runInContext(ts.transpile(handler+'globalThis.run=clearSongLyrics;',{target:ts.ScriptTarget.ES2022}),context);
  await context.run();
  assert.equal(saved.length,1);assert.equal(saved[0].file,'current.wav');assert.equal(saved[0].rows.length,0);
  assert.equal(storage.get('uvr-lyrics-draft:other.wav'),'keep');
  assert.equal(storage.get('uvr-passages-v3:other.wav:row'),'keep');
  if(fail){assert.equal(loaded.length,0);assert.equal(storage.get('uvr-lyrics-draft:current.wav'),'old');}
  else {assert(!storage.has('uvr-lyrics-draft:current.wav'));assert.equal(loaded.length,switchSong?0:1);}
  assert.deepEqual(events,['flush','queue','queue']);
}
(async()=>{await check();await check(true);await check(false,true);console.log('PASS clear current song only: ordered save, scoped caches, failed save preserves rows, switched song untouched');})().catch(e=>{console.error(e);process.exitCode=1});
