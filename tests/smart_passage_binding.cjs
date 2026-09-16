const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ts=require('../frontend/node_modules/typescript');
function load(path,require=()=>({})){const ctx={exports:{},require};vm.createContext(ctx);vm.runInContext(ts.transpile(fs.readFileSync(path,'utf8'),{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}),ctx);return ctx.exports;}
const timing=load('frontend/src/lib/karaoke-timing.ts');
const passages=load('frontend/src/lib/audio-passages.ts',()=>timing);
const context={exports:{},require:()=>passages,AbortController};
vm.createContext(context);vm.runInContext(ts.transpile(fs.readFileSync('frontend/src/lib/smart-passage-binding.ts','utf8'),{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}),context);
const {smartBindRow,fullyBound,bindingLimits}=context.exports;
const word=(word,start,end)=>({word,start,end,timing_source:'manual',needs_review:false});
const match=(index,start,end,score=.9)=>({index,start,end,score});
const make=()=>[
 {text:'ÖNCEKİ',start:7,end:9.9,words:[word('ÖNCEKİ',7,9.9)]},
 {text:'GÖZLERİM YOLDA, DİLİM DUADA,',start:10,end:14,words:[word('GÖZLERİM',10,10),word('YOLDA,',11,12),word('DİLİM',12,13),word('DUADA,',14,14)]},
 {text:'SONRAKİ',start:14.4,end:16,words:[word('SONRAKİ',14.4,16)]}];
const run=(rows,analyze,signal=new AbortController().signal)=>smartBindRow(rows,1,20,analyze,signal,()=>{});
(async()=>{
 let rows=make(),snapshot=JSON.stringify(rows),calls=[];
 const result=await run(rows,async target=>{
   calls.push(target);assert.equal(target.text,rows[1].text);
   if(calls.length===1)return {word_times:[]};
   return {word_times:[match(0,9.95,10.8),match(1,10.9,11.8),match(2,12.1,12.9),match(3,13.2,14.1)]};
 });
 assert.equal(result.attempts,2);assert.equal(result.complete,true);assert.equal(result.expanded,true);
 assert.equal(result.segment.start,9.95);assert.equal(result.segment.end,14.1);
 assert.equal(JSON.stringify(result.segment.words.slice(1,3)),JSON.stringify(rows[1].words.slice(1,3)));
 assert.equal(JSON.stringify(rows),snapshot);
 assert.equal(calls[1].start,9.9,'never enter previous row');assert.equal(calls[1].end,14.15);
 const completeRows=[rows[0],result.segment,rows[2]];
 const skipped=await run(completeRows,()=>assert.fail('complete row must not be scanned'));
 assert.equal(skipped.attempts,0);assert.equal(skipped.segment,result.segment);
 rows=make();rows[1].locked=true;
 assert.equal((await run(rows,()=>assert.fail('locked row must not be scanned'))).segment,rows[1]);
 rows=make();calls=[];
 const failed=await run(rows,async target=>{calls.push(target);return {word_times:[match(0,9.95,10.7)]};});
 assert.equal(calls.length,4);assert.equal(failed.segment,rows[1],'failed expansion restores exact original');
 assert.ok(calls.every(r=>r.start>=9.9&&r.end<=14.4));
 const partial=await run(make(),async()=>({word_times:[match(0,10.1,10.8)]}));
 assert.equal(partial.complete,false);assert.equal(partial.segment.start,10);assert.equal(partial.segment.end,14);
 assert.equal(partial.segment.words[0].start,10.1);assert.equal(partial.segment.words[3].end,14);
 rows=make();
 const bad=await run(rows,async()=>({word_times:[match(0,9.8,10.8),match(3,13.1,14.5),match(9,13.2,13.5)]}));
 assert.equal(bad.segment,rows[1],'out-of-row and extra words are rejected');
 const wrong=await run(make(),async()=>({word_times:[match(0,10.1,11.5),match(3,13.1,13.8,.1)]}));
 assert.equal(wrong.complete,false);assert.equal(wrong.segment.words[0].end,10,'existing neighbour word protected');
 rows=make();rows[0]={text:'BİLİNMİYOR',start:0,end:0};rows[2]={text:'BİLİNMİYOR',start:0,end:0};
 assert.equal(bindingLimits(rows,1,20).start,10);assert.equal(bindingLimits(rows,1,20).end,14);
 rows=make();rows[1]={text:'İLK SON',start:10,end:14};calls=[];
 assert.equal((await run(rows,async r=>{calls.push(r);return {word_times:[match(0,10.2,11),match(1,12,13)]};})).complete,true);
 assert.equal(calls.length,1,'stop immediately when all words match');
 rows=make();rows[1]={text:'İLK SON',start:10,end:14};
 const accepted=[match(0,10.2,10.23,.2),match(1,12,13,.33)];
 const single=passages.bindDetectedWords(rows[1],accepted);
 const bulk=await run(rows,async()=>({word_times:accepted}));
 assert.equal(bulk.complete,true,'single-row accepted short/medium confidence words must also complete bulk');
 assert.equal(bulk.attempts,1);
 assert.equal(JSON.stringify(bulk.segment.words),JSON.stringify(single.words),'single and bulk use identical word binding');
 // Acoustic result captured from the user's Ezo recording: formerly discarded by bulk's .5 cutoff.
 const ezo={text:'NE OLUR DÖN GEL EZO',start:83.3685,end:88.68589,words:[
   word('NE',83.68953082616694,83.78985898258675),
   word('OLUR',84.39182792110554,84.7730749155008),
   word('DÖN',84.87340307192059,85.35497822273564),
   word('GEL',85.57570016685919,85.7763564796988),word('EZO',83.3685,83.3685)]};
 const ezoTimes=[match(4,86.11747221152612,86.45858794335345,.33239517609278363)];
 const ezoResult=await smartBindRow([ezo],0,300,async()=>({word_times:ezoTimes}),new AbortController().signal,()=>{});
 assert.equal(ezoResult.complete,true);
 assert.equal(ezoResult.attempts,1);
 assert.equal(JSON.stringify(ezoResult.segment.words),JSON.stringify(passages.bindDetectedWords(ezo,ezoTimes).words));
 assert.equal(JSON.stringify(ezoResult.segment.words.slice(0,4)),JSON.stringify(ezo.words.slice(0,4)));
 const abort=new AbortController();abort.abort();
 const backwards=[{text:'ÖNCE',start:248,end:253},{text:'HEDEF',start:253,end:261},
   {text:'SONRA',start:261,end:269},{text:'SON',start:250,end:250.5}];
 assert.equal(bindingLimits(backwards,1,277).end,261,'unbound backwards final row cannot block earlier rows');
 const repaired=await smartBindRow(backwards,3,277,async target=>{
   assert.equal(target.start,269);assert.equal(target.end,277);
   return {word_times:[match(0,270,275)]};
 },new AbortController().signal,()=>{});
 assert.equal(repaired.complete,true);assert.equal(repaired.segment.start,269);
 const unchanged=await smartBindRow(backwards,3,277,async()=>({word_times:[]}),new AbortController().signal,()=>{});
 assert.equal(unchanged.segment,backwards[3],'failed automatic repair leaves original untouched');
 const protectedRows=structuredClone(backwards);protectedRows[3].words=[word('SON',250,250.5)];
 assert.equal(bindingLimits(protectedRows,1,277).end,250,'existing linked audio must never be ignored');
 const punctuation={text:'OY EZO ! TUTMUYOR , DİZİM EZO',start:0,end:10};
 const punctTimes=[0,1,3,5,6].map((index,i)=>match(index,i+1,i+1.5));
 const punctResult=await smartBindRow([punctuation],0,20,async()=>({word_times:punctTimes}),new AbortController().signal,()=>{});
 assert.equal(punctResult.complete,true,'standalone punctuation must not require nonexistent audio');
 assert.equal(punctResult.attempts,1);
 assert.equal(punctResult.segment.text,punctuation.text);
 assert.equal(punctResult.segment.words[3].word,'TUTMUYOR');
 assert.equal(punctResult.segment.words[3].start,3);
 await assert.rejects(run(make(),()=>assert.fail('aborted'),abort.signal));
 assert.equal(fullyBound({text:'İLK SON',start:1,end:3,words:[word('İLK',2,3),word('SON',1,2)]}),false);
 console.log('PASS: skip complete/locked, four bounded attempts, preserve all existing links, restore failed expansion, no neighbouring text or audio imported');
})().catch(e=>{console.error(e);process.exitCode=1});
