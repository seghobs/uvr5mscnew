const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),ts=require('../frontend/node_modules/typescript');
function lib(file){const ctx={exports:{}};vm.createContext(ctx);vm.runInContext(ts.transpile(fs.readFileSync(file,'utf8'),{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}),ctx);return ctx.exports;}
const {recordLiveRow,clearLiveTimings,clearRowTimings}=lib('frontend/src/lib/live-sync.ts');
const {repairTiming,rowPlaybackRange}=lib('frontend/src/lib/karaoke-timing.ts');
const tree=ts.createSourceFile('modal.tsx',fs.readFileSync('frontend/src/components/KaraokeStudioModal.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
const bodies={};function visit(n){if(ts.isVariableDeclaration(n)&&['finishLiveRow','down','up','blur','seekTo','resumeLiveSyncFromRow','stepCurrentTime','undoAllLiveSync'].includes(n.name.getText(tree)))bodies[n.name.getText(tree)]=n.initializer.getText(tree);ts.forEachChild(n,visit);}visit(tree);
let saved;
const old={start:23,end:24,text:'BİR İKİ',words:[{word:'BİR',start:23,end:23,timing_source:'estimated'},{word:'İKİ',start:23,end:23,timing_source:'estimated'}]};
const ctx={clearLiveTimings,liveSpaceHandledRef:{current:false},recordLiveRow,segmentsRef:{current:[old,{...old,text:'ÜÇ'}]},liveCaptureRef:{current:{index:0,start:51.8}},liveGesture:'tap',liveSyncIndex:0,
 liveSyncFinishedRef:{current:false},stopWordPreview(){},wordPreviewEndRef:{current:null},linePreviewEndRef:{current:null},loopLineRef:{current:null},setLoopLineIndex(){},editedPlaybackStartRef:{current:null},
 audioRef:{current:{currentTime:55.6,paused:false,pause(){this.paused=true;},play(){return Promise.resolve();}}},
 setIsSpacePressed(){},setSpacePressStartTime(){},setSegments(s){ctx.rows=repairTiming(s);},triggerAutoSave(s){saved=s;},preservePassages(){},vocalStem:'test',instStem:'',setLiveSyncIndex(i){ctx.liveSyncIndex=i;},rowRefs:{current:{}},setIsLiveSyncMode(){},onNotify(){},isLiveSyncMode:true,typing:()=>false,handleLiveSyncPrev(){},handleLiveSyncNext(){},toggleMasterPlay(){}};
vm.createContext(ctx);for(const [name,body] of Object.entries(bodies))vm.runInContext(ts.transpile(`globalThis.${name}=${body}`,{target:ts.ScriptTarget.ES2020}),ctx);
const event={code:'Space',repeat:false,preventDefault(){},stopImmediatePropagation(){}};
ctx.down(event);ctx.up(event);
assert.equal(saved[0].start,51.8);assert.equal(saved[0].end,55.6);
assert.equal(rowPlaybackRange(ctx.rows[0]).start,51.8);
assert.equal(rowPlaybackRange(ctx.rows[0]).end,55.6);
assert.equal(ctx.liveCaptureRef.current.start,55.6);assert.equal(ctx.liveSyncIndex,1);
ctx.down({...event,repeat:true});assert.equal(ctx.liveSyncIndex,1);
ctx.liveGesture='hold';ctx.liveCaptureRef.current=null;ctx.audioRef.current.currentTime=60;
ctx.down(event);ctx.audioRef.current.currentTime=63;ctx.up(event);
assert.equal(saved[1].start,60);assert.equal(saved[1].end,63);
assert.equal(old.start,23);
assert.throws(()=>recordLiveRow(old,4,4));
console.log('PASS: Space tap completes unlinked row, key-up does not double-advance, repeats ignored, hold records exact range');

// Clear uses current lyrics and removes every row and word timestamp.
Object.assign(ctx,{stopWordPreview(){},wordPreviewEndRef:{current:99},linePreviewEndRef:{current:99},loopLineRef:{current:1},editedPlaybackStartRef:{current:99},setLoopLineIndex(){},seekTo(t){ctx.seek=t;}});
const texts=ctx.segmentsRef.current.map(s=>s.text);
ctx.undoAllLiveSync();
assert.deepEqual(saved.map(s=>s.text),texts);
for(const row of saved){assert.equal(row.start,0);assert.equal(row.end,0);for(const w of row.words){assert.equal(w.start,0);assert.equal(w.end,0);assert.equal(w.needs_review,true);}}
assert.equal(ctx.seek,0);assert.equal(ctx.liveCaptureRef.current,null);
assert.equal(ctx.linePreviewEndRef.current,null);assert.equal(ctx.audioRef.current.paused,true);
assert.equal(old.start,23);
console.log('PASS: clear all preserves current lyrics, clears row/word timings, saves, stops playback and leaves original objects intact');
ctx.isLiveSyncMode=true;ctx.typing=()=>true;ctx.liveGesture='tap';
ctx.liveCaptureRef.current={index:0,start:70};ctx.audioRef.current.currentTime=74;ctx.audioRef.current.paused=false;
let stopped=0;const focusedEvent={...event,stopImmediatePropagation(){stopped++;}};
ctx.down(focusedEvent);ctx.up(focusedEvent);
assert.equal(saved[0].start,70);assert.equal(saved[0].end,74);assert.equal(stopped,2);
ctx.isLiveSyncMode=false;const lastSaved=saved;ctx.down(focusedEvent);assert.equal(saved,lastSaved);
ctx.liveSpaceHandledRef.current=true;ctx.up(focusedEvent);assert.equal(ctx.liveSpaceHandledRef.current,false);
console.log('PASS: live Space works with editable focus, consumes down/up, normal text editing remains available outside live sync');
ctx.isLiveSyncMode=true;ctx.liveGesture='tap';ctx.typing=()=>false;
ctx.liveCaptureRef.current={index:0,start:80};ctx.audioRef.current.currentTime=84;ctx.audioRef.current.paused=true;
ctx.down(event);assert.equal(saved[0].start,80);assert.equal(saved[0].end,84);assert.equal(ctx.liveSyncIndex,1);
ctx.liveCaptureRef.current={index:0,start:90};ctx.audioRef.current.currentTime=90;ctx.audioRef.current.paused=true;
const previousSave=saved;ctx.down(event);assert.equal(saved,previousSave);assert.equal(ctx.liveCaptureRef.current.start,90);
ctx.blur();assert.equal(ctx.liveCaptureRef.current.start,90);
ctx.audioRef.current.currentTime=94;ctx.audioRef.current.paused=false;ctx.down(event);assert.equal(saved[0].start,90);assert.equal(saved[0].end,94);
ctx.liveGesture='hold';ctx.blur();assert.equal(ctx.liveCaptureRef.current,null);
console.log('PASS: first paused tap records boundary, zero elapsed keeps start, focus loss preserves tap capture and cancels hold');
// Reinstall the actual seek handler after the clear-test stub.
vm.runInContext(ts.transpile(`globalThis.seekTo=${bodies.seekTo}`,{target:ts.ScriptTarget.ES2020}),ctx);
ctx.duration=200;ctx.setCurrentTime=()=>{};ctx.isLiveSyncMode=true;ctx.liveGesture='tap';ctx.liveSyncIndex=0;
ctx.seekTo(51);assert.equal(ctx.liveCaptureRef.current.start,51);
ctx.audioRef.current.currentTime=55;ctx.audioRef.current.paused=false;ctx.down(event);
assert.equal(saved[0].start,51);assert.equal(saved[0].end,55);
ctx.liveSyncIndex=0;ctx.stepCurrentTime(2);assert.equal(ctx.liveCaptureRef.current.start,57);
ctx.audioRef.current.currentTime=60;ctx.down(event);assert.equal(saved[0].start,57);assert.equal(saved[0].end,60);
console.log('PASS: live timeline seek and +/-2 seconds arm capture immediately; very first Space completes the row');
ctx.rowPlaybackRange=rowPlaybackRange;ctx.setActiveTab=()=>{};ctx.setShowAdvancedTools=()=>{};
ctx.startLiveSyncMode=i=>{ctx.liveSyncIndex=i;ctx.liveCaptureRef.current={index:i,start:ctx.audioRef.current.currentTime};};
ctx.segmentsRef.current=[{...old},recordLiveRow({...old,text:'DÜZELTİLEN SÖZ'},51.5,56)];
const untouched=ctx.segmentsRef.current[0];ctx.resumeLiveSyncFromRow(1);
assert.equal(ctx.audioRef.current.currentTime,51.5);assert.equal(ctx.liveSyncIndex,1);assert.equal(ctx.liveCaptureRef.current.start,51.5);
ctx.audioRef.current.currentTime=57;ctx.down(event);assert.equal(saved[1].end,57);assert.equal(saved[0],untouched);
ctx.segmentsRef.current=clearLiveTimings([old]);ctx.audioRef.current.currentTime=82;ctx.resumeLiveSyncFromRow(0);assert.equal(ctx.liveCaptureRef.current.start,82);
console.log('PASS: continue corrected row from its exact start, retain previous rows, use playhead for untimed rows');
// Enter cancels the active capture even with editable focus or Space held down.
for(const gesture of ['tap','hold'])for(const code of ['Enter','NumpadEnter']){
  ctx.isLiveSyncMode=true;ctx.liveGesture=gesture;ctx.typing=()=>true;
  ctx.liveCaptureRef.current={index:0,start:80};ctx.liveSpaceHandledRef.current=true;
  ctx.audioRef.current.currentTime=84;ctx.audioRef.current.paused=false;
  ctx.wordPreviewEndRef.current=99;ctx.linePreviewEndRef.current=99;
  ctx.loopLineRef.current=0;ctx.editedPlaybackStartRef.current=80;
  let pressed=true,pressStart=80,previewStopped=false,modeClosed=false;
  ctx.setIsSpacePressed=v=>{pressed=v;};ctx.setSpacePressStartTime=v=>{pressStart=v;};
  ctx.setIsLiveSyncMode=v=>{modeClosed=!v;ctx.isLiveSyncMode=v;};
  ctx.stopWordPreview=()=>{previewStopped=true;};
  const beforeRows=JSON.stringify(ctx.segmentsRef.current),beforeSaved=saved;
  let prevented=false,consumed=false;
  ctx.down({...event,code,preventDefault(){prevented=true;},stopImmediatePropagation(){consumed=true;}});
  assert.ok(modeClosed&&prevented&&consumed&&previewStopped);
  assert.equal(ctx.liveCaptureRef.current,null);assert.equal(ctx.audioRef.current.paused,true);
  assert.equal(pressed,false);assert.equal(pressStart,null);
  assert.equal(ctx.wordPreviewEndRef.current,null);assert.equal(ctx.linePreviewEndRef.current,null);
  assert.equal(ctx.loopLineRef.current,null);assert.equal(ctx.editedPlaybackStartRef.current,null);
  ctx.up(event);
  assert.equal(ctx.liveSpaceHandledRef.current,false);
  assert.equal(saved,beforeSaved);assert.equal(JSON.stringify(ctx.segmentsRef.current),beforeRows);
  prevented=false;consumed=false;
  ctx.down({...event,code,preventDefault(){prevented=true;},stopImmediatePropagation(){consumed=true;}});
  assert.equal(prevented,false);assert.equal(consumed,false);
}
console.log('PASS: Enter exits tap/hold sync, pauses playback, cancels pending capture, preserves saved rows and leaves normal Enter unchanged');
// Passing over a linked row must neither rewrite its envelope nor clear words.
for(const gesture of ['tap','hold'])for(const source of ['manual','ctc','aligned','whisper',undefined]){
  const protectedRow={start:23,end:26,text:'BİR İKİ',words:[
    {word:'BİR',start:23.2,end:24,needs_review:true,timing_source:source,probability:.4},
    {word:'İKİ',start:24,end:24,timing_source:'estimated',needs_review:true}]};
  const snapshot=JSON.stringify(protectedRow),saveBefore=saved;
  assert.equal(recordLiveRow(protectedRow,50,54),protectedRow);
  ctx.segmentsRef.current=[protectedRow,clearLiveTimings([old])[0]];
  ctx.liveGesture=gesture;ctx.isLiveSyncMode=true;ctx.liveSyncIndex=0;
  ctx.liveCaptureRef.current={index:0,start:50};ctx.audioRef.current.currentTime=54;ctx.audioRef.current.paused=false;
  if(gesture==='tap')ctx.down(event);else ctx.up(event);
  assert.equal(ctx.liveSyncIndex,1);assert.equal(ctx.segmentsRef.current[0],protectedRow);
  assert.equal(saved,saveBefore);assert.equal(JSON.stringify(protectedRow),snapshot);
  // The next unlinked row remains editable; saving it also preserves its neighbor.
  ctx.liveCaptureRef.current={index:1,start:54};ctx.audioRef.current.currentTime=58;
  if(gesture==='tap')ctx.down(event);else ctx.up(event);
  assert.equal(saved[0],protectedRow);assert.equal(saved[1].start,54);assert.equal(saved[1].end,58);
  assert.equal(JSON.stringify(saved[0]),snapshot);
  assert.equal(ctx.isLiveSyncMode,false);assert.equal(ctx.liveSyncIndex,1);
  assert.equal(ctx.liveCaptureRef.current,null);assert.equal(ctx.audioRef.current.paused,true);
  ctx.typing=()=>false;
  let toggled=false,blocked=0;ctx.toggleMasterPlay=()=>{toggled=true;};
  const finishedSave=saved;
  for(let i=0;i<2;i++){
    ctx.down({...event,preventDefault(){blocked++;}});ctx.up(event);
  }
  assert.equal(blocked,2);assert.equal(toggled,false);assert.equal(ctx.liveSyncIndex,1);
  assert.equal(saved,finishedSave);assert.equal(ctx.audioRef.current.paused,true);
}
console.log('PASS: protected rows survive; final row finishes sync and repeated Space cannot restart playback or move to an earlier row');
// Single-row clear keeps the lyric text, zeroes row/word timings, leaves siblings and the original untouched.
const soloRow={start:12.5,end:15,text:'BİR İKİ',words:[{word:'BİR',start:12.5,end:13.4,timing_source:'manual'},{word:'İKİ',start:13.4,end:15,timing_source:'manual'}]};
const soloSnapshot=JSON.stringify(soloRow);
const clearedRow=clearRowTimings(soloRow);
assert.equal(clearedRow.text,'BİR İKİ');
assert.equal(clearedRow.start,0);assert.equal(clearedRow.end,0);
assert.equal(clearedRow.words.length,2);
for(const w of clearedRow.words){assert.equal(w.start,0);assert.equal(w.end,0);assert.equal(w.timing_source,'estimated');assert.equal(w.needs_review,true);}
assert.equal(JSON.stringify(soloRow),soloSnapshot);
const sibling={start:20,end:22,text:'ÜÇ',words:[{word:'ÜÇ',start:20,end:22,timing_source:'manual'}]};
const rows=[soloRow,sibling].map((s,i)=>i===0?clearRowTimings(s):s);
assert.equal(rows[0].start,0);assert.equal(rows[1],sibling);
console.log('PASS: single-row clear zeroes only that row, preserves text, marks words for review and leaves originals intact');
