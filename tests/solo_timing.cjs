const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),ts=require('../frontend/node_modules/typescript');
const ctx={exports:{}};vm.createContext(ctx);vm.runInContext(ts.transpile(fs.readFileSync('frontend/src/lib/karaoke-timing.ts','utf8'),{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}),ctx);
const lib=ctx.exports;
for(const text of ['SOLO...','solo…',' SOLO ... ']){
 const row={text,start:17,end:21,words:[{word:text,start:17,end:17,timing_source:'estimated',needs_review:true}]};
 const fixed=lib.instrumentalTiming(row),w=fixed.words[0];
 assert.equal(lib.wordFill(w,17),0);assert.equal(lib.wordFill(w,19),.5);assert.equal(lib.wordFill(w,21),1);
 assert.equal(lib.timingIssues([row]).length,0);
 assert.equal(lib.videoSegments([row])[0].words[0].end,21);
 assert.equal(lib.instrumentalTiming({...fixed,end:25}).words[0].end,25);
 assert.equal(row.words[0].end,17);
}
const lyric={text:'SOLO BİR ŞARKI',start:1,end:3};assert.equal(lib.instrumentalTiming(lyric),lyric);
const original={text:'SOLO...',start:17,end:21};
for(const [start,end] of [[18,20],[0,25],[17,19]]){
 const edited=lib.applyEditedWordTimes(original,[{word:'SOLO...',start,end,timing_source:'manual'}]);
 const saved=lib.repairTiming([edited])[0];
 assert.equal(saved.start,start);assert.equal(saved.end,end);
 assert.equal(lib.videoSegments([saved])[0].words[0].end,end);
 assert.equal(lib.wordFill(saved.words[0],(start+end)/2),.5);
}
const ordinary=lib.applyEditedWordTimes(lyric,[{word:'SOLO BİR ŞARKI',start:1.5,end:2.5}]);
assert.equal(ordinary.start,1);assert.equal(ordinary.end,3);
console.log('PASS: solo interval fill, export, changed duration, original lyrics preserved');
