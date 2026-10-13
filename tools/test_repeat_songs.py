"""Full audio repeated-lyric holdout test. No original lyrics DB writes."""
import copy,json,time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from karaoke_supplied_alignment import align_supplied,instrumental
from karaoke_repeat_spotting import text_key
from karaoke_ctc import MODEL_DIR
from tools.test_repeat_web import terminal_expectation
vocab=json.loads((MODEL_DIR/'vocab.json').read_text(encoding='utf8'))
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'cache/supplied_ten'
manifest=json.loads((work/'manifest.json').read_text(encoding='utf8'))
results=[]
selection=sys.argv[1:]
for track in manifest:
    if selection and track['id'] not in selection:continue
    reference=json.loads((work/(track['id']+'-api-result.json')).read_text(encoding='utf8'))['segments']
    seen=set();rows=[];removed=[]
    for row in reference:
        if instrumental(row):continue
        key=row['text'].strip().casefold()
        if key in seen:removed.append(row);continue
        seen.add(key);r=copy.deepcopy(row);r.update(start=0,end=0,words=[],locked=False);rows.append(r)
    removed.extend(terminal_expectation(track,rows))
    started=time.monotonic()
    try:
        result,report=align_supplied(track['file'],rows,instrumental_path=Path(track['file']).with_name(Path(track['file']).name.replace('_Vocals_','_Instrumental_')))
        added=[r for r in result if r.get('id','').startswith('auto-repeat:')]
        def matches(predicted,expected):
            if text_key(predicted,vocab)!=text_key(expected,vocab):return False
            if abs(predicted['start']-expected['start'])<.5:return True
            # An earlier forced path sometimes stretches one word over a music break.
            # Most independently comparable word positions must still agree.
            pw=predicted.get('words') or [];ew=expected.get('words') or []
            if len(pw)!=len(ew) or not pw:return False
            good=sum(abs(a['start']-b['start'])<.5 and abs(a['end']-b['end'])<.5 for a,b in zip(pw,ew))
            return good/len(pw)>=.8
        unmatched=list(removed);correct=[]
        for predicted in added:
            target=next((x for x in unmatched if matches(predicted,x)),None)
            if target is not None:correct.append(predicted);unmatched.remove(target)
        original=[r for r in result if r.get('id') in {x.get('id') for x in rows}]
        assert [r['text'] for r in original]==[r['text'] for r in rows],'Supplied originals changed'

        item={'id':track['id'],'omitted_repeats':len(removed),'added':len(added),'correct':len(correct),'unmatched_additions':len(added)-len(correct),'missing':len(unmatched),'report':report,'seconds':time.monotonic()-started}
        (work/(track['id']+'-repeat-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    except Exception as e:item={'id':track['id'],'error':str(e)}
    results.append(item);print({k:v for k,v in item.items() if k!='report'},flush=True)
    (work/'repeat-whole-song-validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
