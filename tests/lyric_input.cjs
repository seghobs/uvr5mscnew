const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ts=require('../frontend/node_modules/typescript');
function load(file,requireFn=require){const ctx={exports:{},require:requireFn};vm.createContext(ctx);vm.runInContext(ts.transpile(fs.readFileSync(file,'utf8'),{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}),ctx);return ctx.exports;}
const timing=load('frontend/src/lib/karaoke-timing.ts');
const {updateLyricInput}=load('frontend/src/lib/lyric-input.ts',()=>timing);
function check(raw,start,end,direction,expected,expectedStart,expectedEnd){
  let value=raw,s=start,e=end,dir=direction;
  // Like a real input, assigning a changed value moves its cursor to the end.
  const input={get value(){return value;},set value(v){value=v;s=e=v.length;},
    get selectionStart(){return s;},get selectionEnd(){return e;},get selectionDirection(){return dir;},
    setSelectionRange(a,b,d){s=a;e=b;dir=d;}};
  let saved;
  updateLyricInput(input,text=>{saved=text;assert.equal(input.value,text);});
  assert.equal(saved,expected);assert.equal(s,expectedStart);assert.equal(e,expectedEnd);assert.equal(dir,direction);
}
check('BİR yeni ŞARKI',8,8,'none','BİR YENİ ŞARKI',8,8);
check('BİR şarkı SON',4,9,'backward','BİR ŞARKI SON',4,9);
check('ß SON',1,1,'none','SS SON',2,2);
check('BİR  ŞARKI',4,4,'none','BİR  ŞARKI',4,4);
check('ilk\nSON',3,3,'none','İLK\nSON',3,3);
console.log('PASS: Turkish uppercase preserves mid-line caret, selection direction, spaces and multiline edits');
