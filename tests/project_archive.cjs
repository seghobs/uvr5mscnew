const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),ts=require('../frontend/node_modules/typescript');
const storage=new Map(),saved=new Map(),events=[];
const api={
 getSavedLyrics:async file=>{if(!saved.has(file))throw Object.assign(Error('missing'),{status:404});return structuredClone(saved.get(file));},
 saveLyrics:async(file,segments,language)=>{events.push('save:'+file);saved.set(file,{file_name:file,segments,language});},
};
const persistence={flushAllProjects:async()=>events.push('flush-all'),flushProjects:async()=>events.push('flush-disk'),
 projectStorage:{keys:()=>[...storage.keys()],getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)}};
const context={exports:{},require:name=>name==='./api'?{api}:persistence};vm.createContext(context);
vm.runInContext(ts.transpile(fs.readFileSync('frontend/src/lib/project-archive.ts','utf8'),{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}),context);
const {exportProjectArchive,importProjectArchive}=context.exports;
async function main(){
 const item={id:1,filename:'Dil Disoje',stems:['song_Vocals.wav','song_Instrumental.wav']};
 const segments=[{id:'line',start:195,end:196.86,text:'DIL DISOJE',words:[{word:'DIL',start:152.345,end:152.345,timing_source:'estimated',needs_review:true},{word:'DISOJE',start:195,end:196.86,timing_source:'ctc'}]}];
 saved.set(item.stems[0],{file_name:item.stems[0],language:'kmr',segments});saved.set(item.stems[1],saved.get(item.stems[0]));
 storage.set('uvr-video-heading:'+item.stems[0],JSON.stringify({title:'Dil Disoje',artist:'Kürtçe'}));
 storage.set('uvr-alignment-language:'+item.stems[0],'kmr');
 storage.set('uvr-passages-v3:'+item.stems[0]+':line','{"clips":[1,2]}');
 storage.set('uvr-history:other.wav','private other project');storage.set('uvr_library','library');
 const archive=JSON.parse(JSON.stringify(await exportProjectArchive(item)));
 assert.equal(events[0],'flush-all');assert.equal(archive.archive_version,2);assert.equal(Object.keys(archive.karaoke).length,1);
 assert.deepEqual(archive.karaoke[item.stems[0]].segments,segments);assert.equal(Object.keys(archive.project_values).length,3);
 assert.equal(archive.project_values['uvr_library'],undefined);
 saved.clear();storage.clear();events.length=0;
 const imported=await importProjectArchive(archive);
 assert.deepEqual(JSON.parse(JSON.stringify(imported)),item);assert.deepEqual(saved.get(item.stems[0]).segments,segments);
 assert.equal(storage.get('uvr-alignment-language:'+item.stems[0]),'kmr');assert.equal(events.at(-1),'flush-disk');
 assert.deepEqual(JSON.parse(JSON.stringify(await importProjectArchive(item))),item,'old session files remain supported');
 events.length=0;
 await assert.rejects(importProjectArchive({...archive,project_values:{uvr_library:'[]'}}));assert.equal(events.length,0,'validate all keys before writing');
 await assert.rejects(importProjectArchive({...archive,karaoke:{'other.wav':archive.karaoke[item.stems[0]]}}));
 api.getSavedLyrics=async()=>{throw Object.assign(Error('unavailable'),{status:500});};
 await assert.rejects(exportProjectArchive(item),/unavailable/);
 console.log('PASS complete project archive round trip, Kurdish text, word flags, settings, legacy import, unrelated-key rejection, failed export');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
