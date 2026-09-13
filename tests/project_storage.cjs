const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),ts=require('../frontend/node_modules/typescript');
const {indexedDB}=require('../frontend/node_modules/fake-indexeddb');
const crypto=require('node:crypto').webcrypto;
const disk={};let online=true, delayed=null;
const storage=new Map([['uvr_library','[]']]);
const localStorage={get length(){return storage.size;},key(i){return [...storage.keys()][i]??null;},getItem(k){return storage.get(k)??null;},setItem(k,v){storage.set(k,v);},removeItem(k){storage.delete(k);}};
function client(){
 const ctx={exports:{},indexedDB,crypto,localStorage,Map,Set,Promise,console,setInterval:()=>0,
  window:{dispatchEvent(){},addEventListener(){}},CustomEvent:class{},
  fetch:async(url,options)=>{
   if(!online)throw Error('offline');const body=JSON.parse(options.body);
   if(url.endsWith('bootstrap')){for(const[k,v]of Object.entries(body.values))if(!(k in disk))disk[k]=v;return {ok:true,json:async()=>({values:{...disk}})};}
   if(delayed){const wait=delayed;delayed=null;await wait;}
   disk[body.key]=body.value;return {ok:true,json:async()=>({value:body.value})};
  }};
 vm.createContext(ctx);vm.runInContext(ts.transpile(fs.readFileSync('frontend/src/lib/project-storage.ts','utf8'),{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}),ctx);return ctx.exports;
}
(async()=>{
 const first=client();await first.initializeProjects();
 let unblock;delayed=new Promise(resolve=>unblock=resolve);
 first.projectStorage.setItem('uvr-stem-settings:song','old');
 const saving=first.flushProjects();await new Promise(r=>setTimeout(r,10));
 first.projectStorage.setItem('uvr-stem-settings:song','new');unblock();await saving;
 assert.equal(disk['uvr-stem-settings:song'],'new');
 online=false;first.projectStorage.setItem('uvr-history:song',JSON.stringify({text:'recover me'}));
 await assert.rejects(()=>first.flushProjects());
 online=true;const recovered=client();await recovered.initializeProjects();
 assert.equal(JSON.parse(recovered.projectStorage.getItem('uvr-history:song')).text,'recover me');
 const large='x'.repeat(6*1024*1024);
 recovered.projectStorage.setItem('uvr-history:large-song',large);await recovered.flushProjects();
 assert.equal(disk['uvr-history:large-song'].length,large.length);
 assert.ok(!storage.has('uvr-history:large-song'));
 recovered.projectStorage.removeItem('uvr-history:song');await recovered.flushProjects();
 const reopened=client();await reopened.initializeProjects();assert.equal(reopened.projectStorage.getItem('uvr-history:song'),null);
 console.log('PASS newer in-flight edit, offline recovery, 6 MB project, deletion survives reload');
})().catch(e=>{console.error(e);process.exitCode=1;});
