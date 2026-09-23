const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../frontend/node_modules/typescript');
const source = fs.readFileSync('frontend/src/components/AudioPassageEditor.tsx', 'utf8');
const body = source.slice(source.indexOf('  const findWords=async('), source.indexOf('  const listen=async('));

async function run(candidates, {text='NE OLUR DÖN GEL EZO', edited=false, failed=false,clipOnly=false}={}) {
  const calls=[], errors=[], busy=[], revision={current:0};
  const context={rangeStart:83.3685,rangeEnd:88.68589,duration:100,selected:'clip',selectedClip:{id:'clip'},setCandidateClip:()=>{},validRange:(a,b)=>b>a,
    AbortController,Date,Promise,Error,encodeURIComponent,JSON,file:'song.flac',
    detection:{current:null},revision,candidateRevision:{current:0},draft:{segment:{text}},
    setFinding:v=>busy.push(v),setCandidates:()=>{},setNotice:()=>{},setError:e=>errors.push(e),
    setTimeout:fn=>fn(),detect:async bind=>calls.push(bind),
    fetch:async url=>{
      if(url==='/api/lyrics/deep-words')return {ok:true,json:async()=>({task_id:'test'})};
      if(edited)revision.current++;
      return {ok:true,json:async()=>({status:failed?'failed':'completed',error:'failed',result:{candidates,message:'done'}})};
    }};
  vm.createContext(context);
  await vm.runInContext(ts.transpile(body+`\nfindWords(${clipOnly});`,{target:ts.ScriptTarget.ES2022}),context);
  assert.deepEqual(busy,[true,false]);
  return {calls,errors};
}
(async()=>{
  assert.deepEqual((await run([])).calls,[true], 'Empty Whisper result must align existing lyrics');
  assert.deepEqual((await run([{text:'NE OLUR DÖN GEL EZO'}])).calls,[], 'Keep recognition alternatives');
  assert.deepEqual((await run([],{text:' '})).calls,[], 'No invented lyrics for empty text');
  const edited=await run([],{edited:true});
  assert.deepEqual(edited.calls,[], 'Never align stale edits');
  assert.ok(edited.errors.some(e=>e.includes('düzenleme')));
  assert.deepEqual((await run([],{failed:true})).calls,[], 'Backend failures remain visible');
  assert.deepEqual((await run([],{clipOnly:true})).calls,[], 'Empty clip regeneration must never rewrite or align the whole row');
  console.log('Passage search fallback: 6 scenarios passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
