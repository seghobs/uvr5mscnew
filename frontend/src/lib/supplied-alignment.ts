import type {LyricSegment} from './types';
import {isInstrumentalRow} from './smart-passage-binding';

/** New music labels are allowed; supplied sung text and manual links are immutable. */
export function validateSuppliedResult(before:LyricSegment[],after:LyricSegment[]):void {
  const existingIds=new Set(before.map(r=>r.id).filter(Boolean));
  const isNewRepeat=(row:LyricSegment)=>Boolean(row.id?.startsWith('auto-repeat:')&&!existingIds.has(row.id));
  const archived=new Set<string>();
  const key=(text:string)=>text.normalize('NFC').toLocaleLowerCase('tr-TR').replace(/[^\p{L}\p{N}\p{M}]/gu,'');
  for(const target of after)for(const entry of target.repeat_cleanup||[]){
    const original=before.find(r=>r.id===entry.row.id);
    if(!original)continue; // Previously archived rows survive subsequent syncs.
    const reference=after.find(r=>r.id===entry.matched_row_id);
    if(!original.id||original.locked||original.words?.some(w=>w.timing_source==='manual'&&w.end>w.start)
      ||!reference||key(reference.text)!==key(original.text)||entry.row.text!==original.text
      ||entry.reason!=='duplicate_block_without_audio_gap'||entry.bounds.length!==2
      ||!entry.bounds.every(Number.isFinite)||entry.bounds[1]-entry.bounds[0]>.25||entry.bounds[1]-entry.bounds[0]<-.4)
      throw Error('Fazladan tekrarın ses kanıtı doğrulanamadı; sözler korundu.');
    archived.add(original.id);
  }
  const source=before.filter(r=>!isInstrumentalRow(r)&&!archived.has(r.id||'')),result=after.filter(r=>!isInstrumentalRow(r)&&!isNewRepeat(r));
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

/** Restore the exact original text and timings, retaining the user's undo path. */
export function restoreArchivedRepeats(rows:LyricSegment[]):LyricSegment[]{
  const ids=new Set(rows.map(r=>r.id));
  return rows.flatMap(row=>{
    const restored=(row.repeat_cleanup||[]).filter(e=>!ids.has(e.row.id)).map(e=>{ids.add(e.row.id);return e.row;});
    const {repeat_cleanup,...current}=row;
    return [...restored,current];
  });
}
