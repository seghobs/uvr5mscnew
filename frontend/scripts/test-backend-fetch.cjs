const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript');
const path=require('node:path');
function load(file,extra={}){
  const context={exports:{},fetch:(...args)=>global.fetch(...args),Response,DOMException,setTimeout,clearTimeout,...extra};
  vm.createContext(context);vm.runInContext(ts.transpile(fs.readFileSync(path.join(__dirname,'../src/lib',file),'utf8'),{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}),context);return context.exports;
}
(async()=>{
  let submissions=0,polls=0,writes=0,truncated=0;
  const server=http.createServer((req,res)=>{
    if(req.url==='/write'){writes++;req.socket.destroy();return;}
    if(req.url==='/status/truncated'){
      if(++truncated===1){res.writeHead(200,{'Content-Type':'application/json','Content-Length':'1000'});res.write('{"status":');setTimeout(()=>req.socket.destroy(),20);return;}
      res.end(JSON.stringify({status:'completed',result:'body recovered'}));return;
    }
    if(req.method==='POST'){submissions++;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({task_id:'same-job'}));return;}
    if(req.url==='/status/same-job'){
      polls++;
      if(polls>=2&&polls<=4){req.socket.destroy();return;}
      res.setHeader('Content-Type','application/json');res.end(JSON.stringify(polls===1?{status:'processing',progress:.9,message:'working'}:{status:'completed',result:{segments:['preserved']}}));return;
    }
    res.statusCode=404;res.end('{}');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const realFetch=global.fetch,base=`http://127.0.0.1:${server.address().port}`;
  global.fetch=(url,options)=>realFetch(base+url,options);
  try{
    const backend=load('backend-fetch.ts');
    const api=load('api.ts',{require:()=>({...backend,pollBackendTask:(id,onProgress)=>backend.pollBackendTask(id,onProgress,0)})}).api;
    const updates=[];
    const result=await api.alignSuppliedLyrics('song.wav',[],(message,p)=>updates.push({message,p}));
    assert.equal(JSON.stringify(result),JSON.stringify({segments:['preserved']}));
    assert.equal(submissions,1,'never start a second inference job');
    assert.equal(polls,5,'resume polling the same task after a connection reset');
    assert.ok(updates.some(x=>x.message.includes('yeniden deneniyor')&&x.p===90),'preserve progress while reconnecting');
    await assert.rejects(()=>backend.backendFetch('/write',{method:'POST'}));assert.equal(writes,1);
    assert.equal(await backend.pollBackendTask('truncated',()=>{},0),'body recovered');assert.equal(truncated,2);
    let reads=0;global.fetch=async()=>{reads++;return new Response('{}',{status:404});};
    assert.equal((await backend.backendFetch('/missing')).status,404);assert.equal(reads,1);
    const controller=new AbortController();controller.abort();await assert.rejects(()=>backend.backendFetch('/cancel',{signal:controller.signal}));assert.equal(reads,1);
    global.fetch=async()=>new Response(JSON.stringify({status:'failed',error:'real model error'}));
    await assert.rejects(()=>backend.pollBackendTask('failed',()=>{},0),/real model error/);
    const urls=[];global.fetch=async url=>{urls.push(url);return new Response('{}',{status:urls.length===1?502:200});};
    const browser=load('backend-fetch.ts',{window:{location:{hostname:'192.0.2.3'}}});
    assert.equal((await browser.backendFetch('/api/audio/jobs')).status,200);
    assert.deepEqual(urls,['/api/audio/jobs','http://192.0.2.3:8000/api/audio/jobs']);
    console.log('PASS: real TCP resets recovered; one submission; progress retained; writes, aborts and 404 are not retried; model errors remain visible');
  }finally{global.fetch=realFetch;server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
