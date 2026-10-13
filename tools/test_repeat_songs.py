"""Full audio repeated-lyric holdout test. No original lyrics DB writes."""
import copy,json,time
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from karaoke_supplied_alignment import align_supplied,instrumental
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'cache/supplied_ten'
manifest=json.loads((work/'manifest.json').read_text(encoding='utf8'))
results=[]
for track in manifest:
    reference=json.loads((work/(track['id']+'-api-result.json')).read_text(encoding='utf8'))['segments']
    seen=set();rows=[];removed=[]
    for row in reference:
        if instrumental(row):continue
        key=row['text'].strip().casefold()
        if key in seen:removed.append(row);continue
        seen.add(key);r=copy.deepcopy(row);r.update(start=0,end=0,words=[],locked=False);rows.append(r)
    started=time.monotonic()
    try:
        result,report=align_supplied(track['file'],rows,instrumental_path=Path(track['file']).with_name(Path(track['file']).name.replace('_Vocals_','_Instrumental_')))
        added=[r for r in result if r.get('id','').startswith('auto-repeat:')]
        correct=[r for r in added if any(r['text']==x['text'] and abs(r['start']-x['start'])<.5 for x in removed)]
        item={'id':track['id'],'omitted_repeats':len(removed),'added':len(added),'correct':len(correct),'incorrect':len(added)-len(correct),'report':report,'seconds':time.monotonic()-started}
        (work/(track['id']+'-repeat-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    except Exception as e:item={'id':track['id'],'error':str(e)}
    results.append(item);print({k:v for k,v in item.items() if k!='report'},flush=True)
    (work/'repeat-whole-song-validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
