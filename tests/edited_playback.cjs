const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ts=require('../frontend/node_modules/typescript');
const source=fs.readFileSync('frontend/src/components/KaraokeStudioModal.tsx','utf8');
const tree=ts.createSourceFile('modal.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
function body(name){let value;function visit(n){if(ts.isVariableDeclaration(n)&&n.name.getText(tree)===name)value=n.initializer.getText(tree);ts.forEachChild(n,visit);}visit(tree);assert.ok(value);return ts.transpile(`const run=${value}; run;`,{target:ts.ScriptTarget.ES2020});}
const audio={currentTime:23.262,pause(){},play(){this.playedAt=this.currentTime;return Promise.resolve();}};
const context={audioRef:{current:audio},editedPlaybackStartRef:{current:null},loopLineRef:{current:0},wordPreviewEndRef:{current:30},linePreviewEndRef:{current:30},isPlaying:false,isLiveSyncMode:false,
 segments:[{words:[{start:25,end:56.063}]}],getSegmentWords:s=>s.words,stopWordPreview(){},setActivePlayingIndex(){},setIsPlaying(){},setLoopLineIndex(){},setActivePlayingWord(){},setCurrentTime(t){context.position=t;},setSegments(){}};
vm.createContext(context);
const edit=vm.runInContext(body('handleWordTimeChange'),context);
edit(0,0,'start',29.009);
assert.equal(context.editedPlaybackStartRef.current,29.009);
assert.equal(context.loopLineRef.current,null);
// Simulate a late media position update after editing: master play must restore the explicit edit.
audio.currentTime=23.262;
const master=vm.runInContext(body('toggleMasterPlay').replace('const run =','var masterRun =').replace(/run;\s*$/, 'masterRun;'),context);
master();assert.equal(audio.playedAt,29.009);assert.equal(context.editedPlaybackStartRef.current,null);
audio.currentTime=31;master();assert.equal(audio.playedAt,31);
console.log('PASS: edited start survives stale position, loop cleared, subsequent playback resumes normally');
