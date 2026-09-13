import {uppercaseLyric} from './karaoke-timing';

/** Normalize the DOM value before the controlled update so React keeps the caret. */
export function updateLyricInput(input:HTMLInputElement|HTMLTextAreaElement, update:(text:string)=>void) {
  const raw=input.value;
  const start=input.selectionStart,end=input.selectionEnd,direction=input.selectionDirection;
  const text=uppercaseLyric(raw);
  if(text!==raw){
    input.value=text;
    if(start!==null&&end!==null){
      input.setSelectionRange(uppercaseLyric(raw.slice(0,start)).length,uppercaseLyric(raw.slice(0,end)).length,direction??undefined);
    }
  }
  update(text);
}
