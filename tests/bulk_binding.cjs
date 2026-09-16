const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ts=require('../frontend/node_modules/typescript');
const source=fs.readFileSync('frontend/src/components/KaraokeStudioModal.tsx','utf8');
const fn=source.slice(source.indexOf('const bindEveryRow = async'),source.indexOf('const resumeLiveSyncFromRow'));
async function check(abortSecond){
 const rows=[{text:'Bir',start:1,end:2},{text:'İki',start:3,end:4},{text:'Kilitli',start:5,end:6,locked:true}];
 const saved=[],ref={current:rows};let calls=0;
 const context={AbortController,AbortSignal,JSON,Error,console,
  bulkBindingAbort:{current:null},segmentsRef:ref,vocalStem:'test.wav',instStem:'',
  duration:10,audioRef:{current:null},liveCaptureRef:{current:null},stopWordPreview(){},setIsLiveSyncMode(){},
  setBulkBindingStatus(){},setBulkBindingProblems(){},setSegments(){},onNotify(){},
  triggerAutoSave(rows){saved.push(rows)},projectStorage:{getItem(){return null}},poolKey(){return ''},passagePool(){return []},
  validRange:(a,b)=>b>a,bindAllRows:()=>({segments:[...rows],count:0,problems:[]}),
  fullyBound:()=>false,
  smartBindRow:async(rows,index,duration,analyze)=>{await analyze(rows[index]);return {segment:{...rows[index],words:[{word:rows[index].text,start:rows[index].start,end:rows[index].end}]},complete:true,attempts:1};},
  bindDetectedWords:(row)=>({...row,words:[{word:row.text,start:row.start,end:row.end}]}),
  fetch:async()=>{calls++;if(calls===2){assert.equal(saved.length,1,'first row must be saved before second request');if(abortSecond)return {status:409,ok:false,json:async()=>({detail:'busy'})};}return {status:200,ok:true,json:async()=>({word_times:[]})};}
 };
 vm.createContext(context);vm.runInContext(ts.transpile(fn+'globalThis.run=bindEveryRow;', {target:ts.ScriptTarget.ES2022}),context);
 await context.run();assert.equal(calls,2,'locked row must not be analysed');
 assert.ok(saved[0][0].words);assert.equal(saved[0][2],rows[2]);
 if(abortSecond){assert.equal(saved.length,1);assert.equal(ref.current[1],rows[1]);}
 assert.equal(context.bulkBindingAbort.current,null);
}
(async()=>{await check(false);await check(true);console.log('PASS: incremental bulk saves survive later busy response; locked rows skipped');})().catch(e=>{console.error(e);process.exitCode=1});
