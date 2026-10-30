"""Read-only structural audit; does NOT certify acoustic correctness or edit songs."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from karaoke_quality import quality_report
from karaoke_timing import repair_timing


def audit(database,outputs):
    import soundfile as sf
    songs=[];seen=set()
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as db:
        for name,raw in db.execute('SELECT file_name,segments_json FROM lyrics ORDER BY updated_at DESC'):
            if name in seen:continue
            seen.add(name)
            path=outputs/Path(name).name
            try:
                rows=json.loads(raw)
                if not path.is_file():
                    songs.append({'file_name':name,'status':'audio_unavailable','rows':len(rows)});continue
                duration=sf.info(str(path)).duration
                quality=quality_report(repair_timing(rows),duration)
                songs.append({'file_name':name,'rows':len(rows),'duration':duration,**quality})
            except (ValueError,TypeError,KeyError,RuntimeError,OSError) as error:
                songs.append({'file_name':name,'status':'audit_error','reason':str(error)})
    summary={status:sum(song['status']==status for song in songs) for status in ('ready','estimated','needs_review','audio_unavailable','audit_error')}
    return {'mode':'read_only_structural_audit','acoustic_accuracy_measured':False,'songs':songs,'summary':summary}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,default=ROOT/'assets/favorites.db')
    parser.add_argument('--outputs',type=Path,default=ROOT/'outputs')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.database,args.outputs)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['summary']))
