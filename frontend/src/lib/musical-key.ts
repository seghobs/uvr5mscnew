export const NOTE_NAMES=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
const TR=['Do','Do♯','Re','Re♯','Mi','Fa','Fa♯','Sol','Sol♯','La','La♯','Si'];
export function transposeKey(key:string,shift:number,lang='tr'){
  const match=key.trim().replace(/♯/g,'#').replace(/♭/g,'b').match(/^([A-G])([#b]?)(?:\s+(major|minor)|\s*(m))?$/i);
  if(!match)return null;
  const root=NOTE_NAMES.indexOf(match[1].toUpperCase());
  const note=(root+(match[2]==='#'?1:match[2]==='b'?-1:0)+shift%12+12)%12;
  const minor=match[3]?.toLowerCase()==='minor'||!!match[4];
  return `${lang==='tr'?TR[note]:NOTE_NAMES[note]} ${lang==='tr'?(minor?'minör':'majör'):(minor?'minor':'major')}`;
}
