const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),ts=require('../frontend/node_modules/typescript');
function load(file){const ctx={exports:{},structuredClone};vm.createContext(ctx);vm.runInContext(ts.transpile(fs.readFileSync(file,'utf8'),{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}),ctx);return ctx.exports;}
const {transposeKey}=load('frontend/src/lib/musical-key.ts');
assert.equal(transposeKey('A# Minor',2),'Do minör');assert.equal(transposeKey('Bb minor',-2),'Sol♯ minör');assert.equal(transposeKey('C major',9),'La majör');assert.equal(transposeKey('unknown',2),null);
for(let p=-12;p<=12;p++)assert.equal(transposeKey('A# minor',p),transposeKey('A# minor',p+12));
const {EditHistory,protectLockedRows}=load('frontend/src/lib/edit-history.ts');
const history=new EditHistory({text:'a'});history.push({text:'b'},1000);history.push({text:'bc'},1100);assert.equal(history.undo().text,'a');assert.equal(history.redo().text,'bc');history.push({text:'new'},2500);assert.equal(history.undo().text,'bc');history.push({text:'branch'},4000);assert.equal(history.redo(),null);
const restored=new EditHistory({});restored.restore(history.serialize());assert.equal(restored.undo().text,'bc');
const locked={id:'1',locked:true,start:1,end:2,text:'KEEP'};const unlocked={id:'2',start:3,end:4,text:'OLD'};
assert.equal(protectLockedRows([locked,unlocked],[{...locked,text:'BAD'},{...unlocked,text:'NEW'}])[0],locked);
assert.equal(protectLockedRows([locked,unlocked],[])[0],locked);
assert.equal(protectLockedRows([locked,unlocked],[locked,{...unlocked,text:'NEW'}])[1].text,'NEW');
console.log('PASS musical keys, edit history branches, lock protection');

const {segmentSignature}=load('frontend/src/lib/edit-history.ts');
assert.equal(segmentSignature([{id:'x',start:1,end:2,text:'A',words:[{word:'A',start:1,end:2}]}]),segmentSignature([{text:'A',id:'x',locked:false,start:1,end:2,words:[{word:'A',start:1,end:2,probability:null,needs_review:false}]}]));
console.log('PASS history survives server field defaults and JSON property order');

const timing=load('frontend/src/lib/karaoke-timing.ts');
assert.equal(timing.importProject(timing.serializeProject([locked]))[0].locked,true);
assert.equal(timing.importProject(timing.serializeProject([locked]))[0].id,'1');
console.log('PASS exported project retains row locks and identity');
