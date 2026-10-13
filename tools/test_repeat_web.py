"""Production endpoint holdout and idempotence test on the ten local recordings."""
import copy,json,math,os,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import requests
from karaoke_supplied_alignment import instrumental,spoken
from karaoke_repeat_spotting import text_key
from karaoke_ctc import MODEL_DIR
WORK=ROOT/'cache/supplied_ten'
VOCAB=json.loads((MODEL_DIR/'vocab.json').read_text(encoding='utf8'))


def terminal_expectation(track,rows):
    # Separate new EOF regression from the existing 153 saved repeat references.
    # Bounds come from contextual CTC in both audio channels, not human annotation.
    if track['id']!='c5f7f104f362':return []
    source=next(r for r in rows if r['text']=='BU CAN SANA YANAR,')
    return [{**source,'start':255.34,'end':258.96}]


def matches(predicted,expected):
    if text_key(predicted,VOCAB)!=text_key(expected,VOCAB):return False
    if abs(predicted['start']-expected['start'])<.5:return True
    pw=predicted.get('words') or [];ew=expected.get('words') or []
    if len(pw)!=len(ew) or not pw:return False
    good=sum(abs(a['start']-b['start'])<.5 and abs(a['end']-b['end'])<.5 for a,b in zip(pw,ew))
    return good/len(pw)>=.8


def verify(before,result,duration,removed):
    rows=result['segments'];known={r['id'] for r in before}
    originals=[r for r in rows if r.get('id') in known]
    assert [(r['id'],r['text']) for r in originals]==[(r['id'],r['text']) for r in before]
    copies=[r for r in rows if not instrumental(r) and r.get('id') not in known]
    pending=list(removed);matched=[]
    for row in copies:
        parent=next(r for r in before if r['id']==row['repeat_source_id'])
        assert parent['text']==row['text'],'Invented lyric text'
        target=next((r for r in pending if matches(row,r)),None)
        assert target is not None,'Unmatched automatically added row'
        pending.remove(target);matched.append(row)
    assert not pending,'Missing repeat'
    previous=0
    for row in rows:
        assert math.isfinite(row['start']) and math.isfinite(row['end'])
        assert 0<=row['start']<row['end']<=duration,'Invalid row range'
        assert row['start']>=previous-1e-6,'Overlapping rows'
        previous=row['end']
        assert [w['word'] for w in row.get('words') or []]==row['text'].split()
        for word in row.get('words') or []:
            if spoken(word['word']):assert row['start']<=word['start']<word['end']<=row['end'],'Unbound word'
    report=result['alignment_report']
    assert report['target_words']==report['linked_words'],'Unbound lyric word'
    return {'expected_repeats':len(removed),'recovered_repeats':len(matched),'missing_repeats':0,
        'unmatched_added_rows':0,'original_text_and_order_preserved':True,'all_words_bound':True,
        'repaired_word_spans':report.get('repaired_word_spans',0),'review_rows':len(report['review_rows']),
        'uncertain_word_repairs':report.get('uncertain_word_repairs',0),
        'partial_repeat_review_count':len(report.get('repeat_review_candidates',[]))}


def run(session,link,inst,rows):
    body={'file_name':str(link),'instrumental_file_name':str(inst),'segments':rows,'language':'tr'}
    response=session.post('http://127.0.0.1:3000/api/lyrics/align-supplied',json=body,timeout=30)
    response.raise_for_status();task=response.json()['task_id'];deadline=time.monotonic()+240;progress=0
    while time.monotonic()<deadline:
        time.sleep(.5);response=session.get('http://127.0.0.1:3000/status/'+task,timeout=30)
        response.raise_for_status();data=response.json();current=data.get('progress',0)
        assert current>=progress,'Progress moved backwards';progress=current
        if data['status']=='failed':raise RuntimeError(data.get('error'))
        if data['status']=='completed':return {**data['result'],'test_task_id':task}
    raise TimeoutError('Whole-song repeat alignment exceeded four minutes')


def main():
    tracks=json.loads((WORK/'manifest.json').read_text(encoding='utf8'))
    if len(sys.argv)>1:
        assert sys.argv[1] in {track['id'] for track in tracks},'Unknown priority recording'
        tracks.sort(key=lambda track:track['id']!=sys.argv[1])
    session=requests.Session();session.trust_env=False;run_id=uuid.uuid4().hex[:8];reports=[]
    folder=ROOT/'uploads/.supplied-tests';folder.mkdir(exist_ok=True)
    for track in tracks:
        source=Path(track['file']);link=folder/f'repeats_{run_id}_{track["id"]}{source.suffix}'
        assert link.resolve().is_relative_to(ROOT/'uploads')
        os.link(source,link);started=time.monotonic()
        try:
            reference=json.loads((WORK/(track['id']+'-api-result.json')).read_text(encoding='utf8'))['segments']
            seen=set();before=[];removed=[]
            for row in reference:
                if instrumental(row):continue
                key=row['text'].strip().casefold()
                if key in seen:removed.append(row);continue
                seen.add(key);new=copy.deepcopy(row);new.update(start=0,end=0,words=[],locked=False);before.append(new)
            inst=source.with_name(source.name.replace('_Vocals_','_Instrumental_'))
            terminal=terminal_expectation(track,before)
            removed.extend(terminal)
            result=run(session,link,inst,before)
            checks=verify(before,result,track['duration'],removed)
            if terminal:
                tail=next(r for r in result['segments'] if r['text']==terminal[0]['text'] and r['start']>250)
                assert 257.88<=tail['end']<=258.96+.02,'Terminal word borrowed the following SANA'
                assert tail['end']<259.42,'Unheard continuation included'
                assert tail['words'][-1]['needs_review'] or result['alignment_report'].get('uncertain_word_repairs',0)>0,'Uncertainty cleared without local evidence'
                assert result['alignment_report']['terminal_repeats_added']==1
            checks['terminal_prefixes_added']=len(terminal)
            again=run(session,link,inst,result['segments'])
            sung=lambda rows:[(r['id'],r['text']) for r in rows if not instrumental(r)]
            assert sung(again['segments'])==sung(result['segments']),'Second click changed/multiplied repeats'
            assert again['alignment_report']['repeated_rows_added']==0
            assert again['alignment_report']['solo_intervals']==result['alignment_report']['solo_intervals'],'Second click changed music intervals'
            verify(result['segments'],again,track['duration'],[])
            if terminal:
                tail_again=next(r for r in again['segments'] if r['id']==tail['id'])
                assert abs(tail_again['end']-tail['end'])<1e-6,'Second click changed terminal context boundary'
                assert tail_again['words'][-1]['needs_review']==tail['words'][-1]['needs_review'],'Second click changed uncertainty decision'
                assert again['alignment_report']['terminal_repeats_added']==0
                checks['second_click_terminal_end_preserved']=True
            checks['second_click_idempotent']=True
            checks['second_click_all_words_bound']=True
            item={'id':track['id'],'passed':True,'seconds':time.monotonic()-started,'checks':checks,'task_ids':[result['test_task_id'],again['test_task_id']]}
            (WORK/(track['id']+'-repeat-web-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
            print('PASS',track['id'],checks,flush=True)
        except Exception as e:
            item={'id':track['id'],'passed':False,'error':str(e)};print('FAIL',track['id'],str(e),flush=True)
        finally:
            if link.exists() and os.path.samefile(link,source):link.unlink()
            reports.append(item)
            (WORK/'repeat-web-validation.json').write_text(json.dumps({'recordings':reports,'passed':sum(r['passed'] for r in reports),'total':10},ensure_ascii=False,indent=2),encoding='utf8')
    if not all(r['passed'] for r in reports):raise RuntimeError('Repeat web regression failed')

if __name__=='__main__':main()
