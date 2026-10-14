import type {LyricSegment} from './types';
import {isInstrumentalRow} from './smart-passage-binding';

/** New music labels are allowed; supplied sung text and manual links are immutable. */
export function validateSuppliedResult(before:LyricSegment[],after:LyricSegment[]):void {
  const existingIds=new Set(before.map(r=>r.id).filter(Boolean));
  const isNewRepeat=(row:LyricSegment)=>Boolean(row.id?.startsWith('auto-repeat:')&&!existingIds.has(row.id));
  const source=before.filter(r=>!isInstrumentalRow(r)),result=after.filter(r=>!isInstrumentalRow(r)&&!isNewRepeat(r));
  const verifiedPrefixRepair=(row:LyricSegment,original:LyricSegment)=>{
    const proof=row.repeat_prefix_repair;
    if(!proof||!Number.isFinite(proof.start)||proof.end!==proof.start)return false;
    const tokens=original.text.trim().split(/\s+/);
    if(tokens[0]!==proof.word||tokens.slice(1).join(' ')!==row.text)return false;
    const previous=after[after.indexOf(row)-1],last=previous?.words?.at(-1),first=row.words?.[0];
    return !!last&&!!first&&last.word.trim().toLocaleUpperCase('tr-TR')===proof.word.trim().toLocaleUpperCase('tr-TR')
      &&last.end>last.start&&proof.start>=last.start-.05&&proof.start<=last.end+.05
      &&first.start>=last.end&&first.end>first.start;
  };
  for(const row of after.filter(isNewRepeat)){
    const original=before.find(r=>r.id===row.repeat_source_id);
    if(!original||row.locked||(original.text!==row.text&&!verifiedPrefixRepair(row,original)))throw Error('Tekrar satırı doğrulanamadı.');
  }
  if(source.length!==result.length||source.some((row,i)=>row.text!==result[i].text||
    (row.id&&row.id!==result[i].id)))throw Error('Verdiğiniz sözler veya satır sırası değişti; sonuç uygulanmadı.');
  for(const row of before){
    const target=row.id?after.find(r=>r.id===row.id):
      (isInstrumentalRow(row)?after.find(r=>r.text===row.text&&r.start===row.start&&r.end===row.end):result[source.indexOf(row)]);
    if(row.locked&&(!target||row.start!==target.start||row.end!==target.end))
      throw Error('Kilitli satır değişti; sonuç uygulanmadı.');
    if(!target){if(row.locked)throw Error('Kilitli satır eksildi.');continue;}
    if(isInstrumentalRow(row)&&!row.locked)continue;
    (row.words||[]).forEach((word,index)=>{
      if((row.locked||word.timing_source==='manual'&&!word.needs_review)&&word.end>word.start){
        const candidate=target.words?.[index];
        if(!candidate||word.word!==candidate.word||word.start!==candidate.start||word.end!==candidate.end)
          throw Error('Elle doğrulanmış kelime değişti; sonuç uygulanmadı.');
      }
    });
  }
}
