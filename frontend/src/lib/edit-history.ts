import type {LyricSegment} from './types';
export function protectLockedRows(previous:LyricSegment[],next:LyricSegment[]):LyricSegment[]{
 const locked=previous.filter(s=>s.locked);
 if(!locked.length)return next;
 // Refuse a structural replacement that loses the identity of a locked row.
 if(locked.some(row=>!row.id||!next.some(s=>s.id===row.id)))return previous;
 return next.map(row=>locked.find(s=>s.id===row.id)||row);
}
export class EditHistory<T>{
 past:T[]=[];future:T[]=[];current:T;private lastEdit=0;
 constructor(current:T,private limit=60){this.current=structuredClone(current);}
 push(next:T,now=Date.now()){
  if(JSON.stringify(this.current)===JSON.stringify(next))return false;
  if(now-this.lastEdit>650||!this.past.length)this.past=[...this.past,structuredClone(this.current)].slice(-this.limit);
  this.current=structuredClone(next);this.future=[];this.lastEdit=now;return true;
 }
 breakGroup(){this.lastEdit=0;}
 undo(){if(!this.past.length)return null;this.future.unshift(structuredClone(this.current));this.current=this.past.pop()!;this.lastEdit=0;return structuredClone(this.current);}
 redo(){if(!this.future.length)return null;this.past.push(structuredClone(this.current));this.current=this.future.shift()!;this.lastEdit=0;return structuredClone(this.current);}
 restore(data:{past:T[];current:T;future:T[]}){this.past=data.past.slice(-this.limit);this.current=structuredClone(data.current);this.future=data.future.slice(0,this.limit);this.lastEdit=0;}
 serialize(){while(JSON.stringify({past:this.past,current:this.current,future:this.future}).length>4*1024*1024&&(this.past.length||this.future.length)){if(this.past.length)this.past.shift();else this.future.pop();}return {past:this.past,current:this.current,future:this.future};}
}

export function segmentSignature(rows:LyricSegment[]){
 return JSON.stringify(rows.map(row=>({id:row.id??null,locked:!!row.locked,start:row.start,end:row.end,text:row.text,
  words:row.words?.map(w=>({word:w.word,start:w.start,end:w.end,probability:w.probability??null,timing_source:w.timing_source??null,needs_review:!!w.needs_review}))||[]})));
}
