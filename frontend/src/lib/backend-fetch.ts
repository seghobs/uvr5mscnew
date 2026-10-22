/** Retry status reads, never submissions which may already have started work. */
export async function backendFetch(path:string,options?:RequestInit):Promise<Response> {
  const clean=path.startsWith('/')?path:`/${path}`;
  const read=['GET','HEAD'].includes((options?.method||'GET').toUpperCase());
  let lastResponse:Response|undefined,lastError:unknown;
  for(let attempt=0;attempt<(read?3:1);attempt++){
    if(options?.signal?.aborted)throw options.signal.reason||new DOMException('İptal edildi','AbortError');
    try {
      const response=await fetch(clean,read?{cache:'no-store',...options}:options);
      if(response.status<500||!read)return response;
      lastResponse=response;
    }catch(error){
      if(!read||options?.signal?.aborted)throw error;
      lastError=error;
    }
    if(read&&typeof window!=='undefined'){
      const hostname=window.location.hostname;
      const host=['localhost','127.0.0.1','[::1]'].includes(hostname)?'127.0.0.1':hostname;
      try{
        const response=await fetch(`http://${host}:8000${clean}`,{cache:'no-store',...options});
        if(response.status<500)return response;
        lastResponse=response;
      }catch(error){if(options?.signal?.aborted)throw error;lastError=error;}
    }
    if(attempt<2&&read)await new Promise(resolve=>setTimeout(resolve,250*(attempt+1)));
  }
  if(lastResponse)return lastResponse;
  throw lastError||new Error('Sunucuya ulaşılamadı.');
}

export async function pollBackendTask<T>(taskId:string,onProgress:(message:string,progress:number)=>void,interval=1000):Promise<T>{
  let missed=0,lastProgress=0;
  for(let attempt=0;attempt<3600;attempt++){
    await new Promise(resolve=>setTimeout(resolve,interval));
    let response:Response;
    let task:{status:string;progress?:number;message?:string;error?:string;result?:T}|undefined;
    try{
      response=await backendFetch(`/status/${encodeURIComponent(taskId)}`);
      if(response.status>=500)throw Error('Bağlantı kesildi.');
      if(response.ok)task=await response.json();
    }catch{
      if(++missed>=20)throw Error('Sunucu bağlantısı kurulamadı. Görev sunucuda devam ediyor olabilir; mevcut sözler korundu.');
      onProgress('Sunucu bağlantısı yeniden deneniyor; mevcut senkron görevi korunuyor…',lastProgress);
      continue;
    }
    if(!response.ok)throw Error(response.status===404?'Senkron görevi sunucuda bulunamadı; mevcut sözler korundu.':'Senkron görevi sorgulanamadı; mevcut sözler korundu.');
    if(!task)throw Error('Senkron görevi yanıtı okunamadı.');
    missed=0;
    lastProgress=Math.min(100,(Number(task.progress)||0)*100);
    onProgress(task.message||'Senkronlanıyor…',lastProgress);
    if(task.status==='failed'||task.status==='cancelled'||task.status==='interrupted')throw Error(task.error||task.message||'Senkron tamamlanamadı.');
    if(task.status==='completed')return task.result as T;
  }
  throw Error('Senkron bekleme süresi doldu; görev sunucuda devam ediyor olabilir.');
}
