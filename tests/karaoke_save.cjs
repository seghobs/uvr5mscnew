const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ts=require('../frontend/node_modules/typescript');
const file=ts.createSourceFile('KaraokeStudioModal.tsx',fs.readFileSync('frontend/src/components/KaraokeStudioModal.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
const names=['saveToDatabase','flushPendingSave','triggerAutoSave','saveCurrentProject','flushCurrentProject'];
const declarations=[];
function visit(node){if(ts.isVariableDeclaration(node)&&names.includes(node.name.getText(file)))declarations.push(`const ${node.getText(file)};`);ts.forEachChild(node,visit);}
visit(file);assert.equal(declarations.length,names.length);
function client(){
 const disk=new Map(),writes=[];let queue=Promise.resolve();
 const state={saved:'previous save',saving:false,error:''};
 const context={console,structuredClone,Date,JSON,Promise,
  vocalStem:'song.wav',instStem:'instrumental.wav',selectedLyricsLang:'kmr',
  activeSourceRef:{current:'song.wav'},loadedSourceRef:{current:'song.wav'},activeSavesRef:{current:0},
  committedSegments:{current:[]},pendingSaveRef:{current:null},saveTimeoutRef:{current:null},
  repairTiming:structuredClone,protectLockedRows:(_before,next)=>next,
  setIsSavingDb:value=>state.saving=value,setLastSavedTime:value=>state.saved=value,setSaveError:value=>state.error=value,
  onNotify:()=>{},setTimeout:()=>1,clearTimeout:()=>{},
  projectStorage:{getItem:key=>disk.get(key)??null,setItem:(key,value)=>disk.set(key,value),removeItem:key=>disk.delete(key)},
  enqueueLyricsSave:save=>{const next=queue.catch(()=>{}).then(save);queue=next;return next;},
  api:{saveLyrics:async(file,rows,language)=>{writes.push({file,rows,language});}},flushProjects:async()=>{},
 };
 vm.createContext(context);
 vm.runInContext(ts.transpile(declarations.join('\n')+'\nObject.assign(globalThis,{'+names.join(',')+'});',{target:ts.ScriptTarget.ES2020}),context);
 return {context,state,writes,disk};
}
const row=text=>[{start:1,end:2,text,words:[]}];
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function edit(c,text){c.committedSegments.current=row(text);c.triggerAutoSave(c.committedSegments.current);}
async function main(){
 const clean=client();
 clean.context.committedSegments.current=row('stale open editor');
 await clean.context.flushCurrentProject();
 assert.equal(clean.writes.length,0,'restart must not overwrite a newer database with a clean stale editor');
 edit(clean.context,'real pending edit');
 await clean.context.flushCurrentProject();
 assert.equal(clean.writes.length,1,'restart must persist actual pending edits');
 assert.equal(clean.writes[0].rows[0].text,'real pending edit');
 const {context:c,state,writes,disk}=client();
 edit(c,'new lyrics');assert.equal(state.saved,null,'editing immediately invalidates saved status');
 c.api.saveLyrics=async()=>{throw Error('offline');};
 await assert.rejects(c.saveCurrentProject(),/offline/);
 assert.equal(state.saved,null);assert.ok(state.error);assert.ok(disk.has('uvr-lyrics-draft:song.wav'));
 c.api.saveLyrics=async(file,rows,language)=>writes.push({file,rows,language});
 c.flushProjects=async()=>{throw Error('project disk unavailable');};
 await assert.rejects(c.saveCurrentProject(),/disk unavailable/);
 assert.equal(state.saved,null,'lyrics receipt alone is not a complete project save');
 c.flushProjects=async()=>{};
 await c.saveCurrentProject();assert.ok(state.saved);assert.equal(state.error,'');assert.equal(state.saving,false);
 assert.equal(writes.at(-1).language,'kmr');

 let release; c.api.saveLyrics=()=>new Promise(resolve=>release=resolve);
 edit(c,'first');const first=c.saveCurrentProject();await tick();
 edit(c,'latest');release();await first;
 assert.equal(state.saved,null,'old response cannot certify newer edits');
 assert.ok(disk.has('uvr-lyrics-draft:song.wav'));
 c.api.saveLyrics=async(file,rows)=>writes.push({file,rows});
 await c.saveCurrentProject();assert.equal(writes.at(-1).rows[0].text,'latest');assert.ok(state.saved);

 edit(c,'one');c.api.saveLyrics=()=>new Promise(resolve=>release=resolve);
 const one=c.saveCurrentProject();await tick();
 edit(c,'two');const two=c.saveCurrentProject();release();await one;await tick();
 assert.equal(state.saving,true,'one completed request cannot hide a second pending request');
 release();await two;assert.equal(state.saving,false);assert.ok(state.saved);

 c.api.saveLyrics=async(file,rows)=>writes.push({file,rows});
 c.loadedSourceRef.current='';const before=writes.length;await c.saveCurrentProject();assert.equal(writes.length,before);
 c.loadedSourceRef.current='song.wav';c.committedSegments.current=[];await c.saveCurrentProject();
 assert.equal(writes.at(-1).rows.length,0,'intentional deletion must also be saved');
 console.log('PASS actual studio save handlers: dirty state, failure, full project receipt, newer edits, overlapping saves, loading guard, empty project');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
