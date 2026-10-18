const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ts=require('../frontend/node_modules/typescript');
const calls=[];let polls=0;
const segments=[{text:'VERDİĞİM SÖZ',start:0,end:.5}];
const result={segments:[{...segments[0],start:20,end:22}],alignment_report:{linked_words:2,target_words:2,review_rows:[],preserved_rows:0}};
const context={exports:{},require:()=>({}),console,setTimeout:callback=>queueMicrotask(callback),
  fetch:async(path,options)=>{
    calls.push({path,options});
    if(path==='/api/lyrics/align-supplied')return {ok:true,json:async()=>({task_id:'explicit-click'})};
    if(path==='/status/explicit-click')return {ok:true,json:async()=>++polls===1?
      {status:'processing',message:'Senkron',progress:.5}:{status:'completed',result}};
    throw Error('Unexpected transcription/save request: '+path);
  }};
vm.createContext(context);
vm.runInContext(ts.transpile(fs.readFileSync('frontend/src/lib/api.ts','utf8'),{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}),context);
assert.equal(calls.length,0,'loading API must not start alignment');
const guardContext={exports:{},require:()=>({isInstrumentalRow:row=>/^\s*(solo|enstr[üu]mantal|instrumental)[.\s…!]*$/i.test(row.text)})};
vm.createContext(guardContext);vm.runInContext(ts.transpile(fs.readFileSync('frontend/src/lib/supplied-alignment.ts','utf8'),{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}),guardContext);
const before=[{id:'v1',text:'AYNI SÖZ',start:0,end:0},{id:'v2',text:'AYNI SÖZ',start:0,end:0}];
const after=[{id:'auto-solo:x',text:'SOLO...',start:0,end:20},{...before[0],start:20,end:22},{...before[1],start:50,end:52}];
guardContext.exports.validateSuppliedResult(before,after);
const repeated={id:'auto-repeat:test',repeat_source_id:'v1',text:'AYNI SÖZ',start:30,end:32};
guardContext.exports.validateSuppliedResult(before,[...after,repeated]);
assert.throws(()=>guardContext.exports.validateSuppliedResult(before,[...after,{...repeated,text:'YANLIŞ SÖZ'}]));
assert.throws(()=>guardContext.exports.validateSuppliedResult(before,[...after,{...repeated,repeat_source_id:'missing'}]));
assert.throws(()=>guardContext.exports.validateSuppliedResult(before,[after[0],after[2],after[1]]));
assert.throws(()=>guardContext.exports.validateSuppliedResult(before,[after[0],{...after[1],text:'YENİ SÖZ'},after[2]]));
guardContext.exports.validateSuppliedResult([...before,repeated],[...after,repeated]);
assert.throws(()=>guardContext.exports.validateSuppliedResult([...before,repeated],after));
const locked=[{id:'lock',text:'SOLO...',start:0,end:20,locked:true}];
assert.throws(()=>guardContext.exports.validateSuppliedResult(locked,[{...locked[0],end:30}]));

const duplicate={id:'duplicate',text:'AYNI SÖZ',start:0,end:.5};
const retained={id:'retained',text:'AYNI SÖZ',start:20,end:22};
const archive={row:duplicate,matched_row_id:'retained',bounds:[19.9,20],reason:'duplicate_block_without_audio_gap'};
const cleaned={...retained,repeat_cleanup:[archive]};
guardContext.exports.validateSuppliedResult([duplicate,retained],[cleaned]);
assert.equal(JSON.stringify(guardContext.exports.restoreArchivedRepeats([cleaned])),JSON.stringify([duplicate,retained]));
guardContext.exports.validateSuppliedResult([cleaned],[cleaned]);
for(const bad of [{...duplicate,locked:true},{...duplicate,words:[{word:'AYNI',start:1,end:2,timing_source:'manual'}]}]){
  assert.throws(()=>guardContext.exports.validateSuppliedResult([bad,retained],[{...cleaned,repeat_cleanup:[{...archive,row:bad}]}]));
}
assert.throws(()=>guardContext.exports.validateSuppliedResult([duplicate,retained],[{...cleaned,repeat_cleanup:[{...archive,bounds:[10,20]}]}]));
assert.throws(()=>guardContext.exports.validateSuppliedResult([duplicate,retained],[{...cleaned,repeat_cleanup:[{...archive,row:{...duplicate,text:'BAŞKA'}}]}]));

const repairSource={id:'source',text:'HEY GÖNÜL GENE',start:0,end:0};
const previousSource={id:'previous',text:'YAZIMIZ HEY',start:0,end:0};
const alignedSource={...repairSource,start:10,end:12};
const preceding={...previousSource,start:19,end:20,words:[{word:'HEY',start:19.5,end:20}]};
const repaired={id:'auto-repeat:repair',repeat_source_id:'source',text:'GÖNÜL GENE',start:20.2,end:22,
  words:[{word:'GÖNÜL',start:20.2,end:21},{word:'GENE',start:21,end:22}],
  repeat_prefix_repair:{word:'HEY',start:19.5,end:19.5}};
const validateRepair=row=>guardContext.exports.validateSuppliedResult([repairSource,previousSource],[alignedSource,preceding,row]);
validateRepair(repaired);
assert.throws(()=>validateRepair({...repaired,repeat_prefix_repair:null}),'unverified text removal must fail');
assert.throws(()=>validateRepair({...repaired,repeat_prefix_repair:{word:'HEY',start:19.5,end:19.8}}),'a voiced prefix must be preserved');
assert.throws(()=>validateRepair({...repaired,repeat_prefix_repair:{word:'HEY',start:18,end:18}}),'unrelated preceding sound must fail');
assert.throws(()=>validateRepair({...repaired,text:'GENE'}),'only the proven single duplicated token can be removed');
assert.throws(()=>validateRepair({...repaired,locked:true}),'locked rows must be preserved');

(async()=>{
  const progress=[];
  const actual=await context.exports.api.alignSuppliedLyrics('vocal.wav',segments,(message,p)=>progress.push(p));
  assert.deepEqual(JSON.parse(calls[0].options.body).segments,segments);
  assert.equal(calls[0].options.method,'POST');
  assert.equal(actual,result);assert.equal(progress[0],50);
  assert.equal(calls.length,3,'one explicit job; no per-line requests or lyric discovery');
  assert.equal(JSON.parse(calls[0].options.body).language,'auto');
  await context.exports.api.alignSuppliedLyrics('vocal.wav',segments,()=>{},'instrumental.wav','kmr');
  assert.equal(JSON.parse(calls[3].options.body).language,'kmr');
  await context.exports.api.alignSuppliedLyrics('vocal.wav',segments,()=>{},'instrumental.wav','tr');
  assert.equal(JSON.parse(calls[5].options.body).language,'tr');
  console.log('PASS explicit-only supplied lyric submission, no transcription, one whole-song request, progress and result');
})().catch(error=>{console.error(error);process.exitCode=1});
