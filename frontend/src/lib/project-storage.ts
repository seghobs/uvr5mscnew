/** Disk-backed projects; IndexedDB holds only unacknowledged writes, not a second project database. */
type Pending={key:string;value:string|null;version:string;removed_ids?:number[]};
const mirror=new Map<string,string|null>(),pending=new Map<string,Pending>();
let running:Promise<void>|null=null, durableWrites:Promise<void>=Promise.resolve(),booted=false;
let database:Promise<IDBDatabase>|null=null;
const tracked=(key:string)=>key==='uvr_library'||key==='uvr_lang'||key==='uvr_accent'||/^(uvr-passages-v[23]:|uvr-stem-settings:|uvr-history:|uvr-lyrics-draft:)/.test(key);
function db(){return database??=new Promise<IDBDatabase>((resolve,reject)=>{const request=indexedDB.open('uvr-project-outbox',1);request.onupgradeneeded=()=>request.result.createObjectStore('pending',{keyPath:'key'});request.onsuccess=()=>resolve(request.result);request.onerror=()=>{database=null;reject(request.error);};});}
async function writePending(record:Pending,remove=false){const database=await db();await new Promise<void>((resolve,reject)=>{const transaction=database.transaction('pending','readwrite');const store=transaction.objectStore('pending');if(remove)store.delete(record.key);else store.put(record);transaction.oncomplete=()=>resolve();transaction.onerror=()=>reject(transaction.error);transaction.onabort=()=>reject(transaction.error);});}
function announce(error=''){window.dispatchEvent(new CustomEvent('uvr-project-status',{detail:{pending:pending.size,error}}));}
export async function flushProjects():Promise<void>{
 if(running){await running;if(pending.size)return flushProjects();return;}
 running=(async()=>{
  while(pending.size){
   durableWrites=durableWrites.catch(async()=>{for(const record of pending.values())await writePending(record);});
   await durableWrites;
   const record=pending.values().next().value as Pending;
   const response=await fetch('/api/projects/value',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:record.key,value:record.value,removed_ids:record.removed_ids})});
   if(!response.ok)throw Error('Proje diske kaydedilemedi. Bekleyen değişiklikler korunuyor.');
   const saved=await response.json();
   if(pending.get(record.key)?.version===record.version){
    if('value' in saved)mirror.set(record.key,saved.value);
    window.dispatchEvent(new CustomEvent('uvr-project-changed',{detail:{key:record.key}}));
    // Serialize deletion with later writes so a newer edit cannot be removed from the outbox.
    durableWrites=durableWrites.then(async()=>{if(pending.get(record.key)?.version===record.version){await writePending(record,true);if(pending.get(record.key)?.version===record.version)pending.delete(record.key);}});
    await durableWrites;
   }
   announce();
  }
 })();
 try{await running;}catch(error){announce((error as Error).message);throw error;}finally{running=null;}
}
function change(key:string,value:string|null){
 if(!tracked(key)){if(value===null)localStorage.removeItem(key);else localStorage.setItem(key,value);return;}
 let removed_ids:number[]|undefined;
 if(key==='uvr_library'){try{const before=JSON.parse(mirror.get(key)??localStorage.getItem(key)??'[]');const after=JSON.parse(value||'[]');removed_ids=[...new Set([...(pending.get(key)?.removed_ids||[]),...before.filter((item:{id:number})=>!after.some((next:{id:number})=>next.id===item.id)).map((item:{id:number})=>item.id)])];}catch{}}
 mirror.set(key,value);
 const record={key,value,version:crypto.randomUUID(),removed_ids};pending.set(key,record);announce();
 durableWrites=durableWrites.catch(()=>{}).then(()=>writePending(record));
 void durableWrites.then(()=>{if(booted)return flushProjects();}).catch(()=>announce('Yerel kayıt bekliyor. Bu pencereyi kapatmadan yeniden deneyin.'));
}
export const projectStorage={
 getItem(key:string){return mirror.has(key)?mirror.get(key)!:localStorage.getItem(key);},
 setItem:change,
 removeItem(key:string){change(key,null);},
 keys(){return [...new Set([...mirror.keys(),...Array.from({length:localStorage.length},(_,i)=>localStorage.key(i)!)])];}
};
export async function initializeProjects(){
 const database=await db();
 const recovered=await new Promise<Pending[]>((resolve,reject)=>{const request=database.transaction('pending').objectStore('pending').getAll();request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
 for(const record of recovered){if(!pending.has(record.key))pending.set(record.key,record);}
 const legacy:Record<string,string>={};
 for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i)!;if(tracked(key))legacy[key]=localStorage.getItem(key)!;}
 // Migrate the previous small outbox as well, if this checkout has used it.
 try{for(const [key,value] of Object.entries(JSON.parse(localStorage.getItem('uvr-project-outbox-v1')||'{}'))){if(tracked(key)&&!pending.has(key)){const record={key,value:value as string|null,version:crypto.randomUUID()};pending.set(key,record);await writePending(record);}}}catch{}
 const response=await fetch('/api/projects/bootstrap',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({values:legacy})});
 if(!response.ok)throw Error('Yerel proje deposuna bağlanılamadı. Sunucuyu kontrol edip tekrar deneyin.');
 const values=(await response.json()).values as Record<string,string|null>;
 for(const [key,value] of Object.entries(values))if(tracked(key))mirror.set(key,value);
 for(const record of pending.values())mirror.set(record.key,record.value);
 booted=true;await flushProjects();
 // Confirmed disk copies replace large legacy browser entries; no project files are deleted.
 for(const key of Object.keys(legacy))if(key in values)localStorage.removeItem(key);
 localStorage.removeItem('uvr-project-outbox-v1');
}
const flushers=new Set<()=>Promise<void>>();
export function registerProjectFlusher(flusher:()=>Promise<void>){flushers.add(flusher);return ()=>{flushers.delete(flusher);};}
export async function flushAllProjects(){for(const flusher of flushers)await flusher();await flushProjects();}
if(typeof window!=='undefined'){
 window.addEventListener('beforeunload',e=>{if(pending.size){e.preventDefault();e.returnValue='';}});
 window.addEventListener('online',()=>{if(booted)void flushProjects().catch(()=>{});});
 setInterval(()=>{if(booted&&pending.size)void flushProjects().catch(()=>{});},5000);
}
