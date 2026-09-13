const activePreviews=new Set<string>();
if(typeof window!=='undefined')window.addEventListener('pagehide',()=>{for(const id of activePreviews)void fetch(`/api/audio/jobs/${id}`,{method:'DELETE',keepalive:true}).catch(()=>{});});
export type AudioJob={id:string;kind:string;status:string;message:string;progress:number;file_name:string;pitch:number;tempo:number;cached:boolean;output_file?:string;};
async function json(response:Response){const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'İşlem tamamlanamadı.');return data;}
export async function runAudioJob(body:Record<string,unknown>,signal?:AbortSignal,onStatus?:(job:AudioJob)=>void):Promise<AudioJob>{
  let id='';
  const cancel=()=>{if(id)void fetch(`/api/audio/jobs/${id}`,{method:'DELETE',keepalive:true}).catch(()=>{});};
  signal?.addEventListener('abort',cancel);
  try{
    if(signal?.aborted)throw new DOMException('İptal edildi','AbortError');
    // Receive the ID even if selection changes during submission, then cancel that exact job.
    let job=await json(await fetch('/api/audio/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})) as AudioJob;
    id=job.id;if(body.kind!=='export')activePreviews.add(id);
    while(true){
      if(signal?.aborted){cancel();throw new DOMException('İptal edildi','AbortError');}
      onStatus?.(job);
      window.dispatchEvent(new Event('uvr-jobs-changed'));
      if(job.status==='completed')return job;
      if(['cancelled','failed','interrupted'].includes(job.status))throw Error(job.message);
      await new Promise<void>((resolve,reject)=>{
        const abort=()=>{clearTimeout(timer);reject(new DOMException('İptal edildi','AbortError'));};
        const timer=setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve();},600);
        signal?.addEventListener('abort',abort,{once:true});
      });
      job=await json(await fetch(`/api/audio/jobs/${id}`,{signal}));
    }
  }finally{activePreviews.delete(id);signal?.removeEventListener('abort',cancel);}
}
