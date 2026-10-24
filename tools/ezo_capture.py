"""Preserve this running Ezo job's predictions for local A/B work, read-only."""
import json
from pathlib import Path
import shutil
import time
import urllib.request
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'cache/ezo_karaoke'


def main():
    WORK.mkdir(exist_ok=True)
    destination=WORK/'captured';destination.mkdir(exist_ok=True)
    seen={};stable={}
    while True:
        with urllib.request.urlopen('http://127.0.0.1:8000/api/audio/jobs',timeout=5) as r:data=json.load(r)
        jobs=[job for job in data.get('other_jobs',[]) if 'Ezo' in str(job.get('separation_request',{}))]
        for folder in (ROOT/'outputs').glob('atlas_*'):
            if not (folder/'atlas_input.wav').exists():continue
            for source in folder.glob('*.wav'):
                name=source.name
                lower=name.lower()
                if not any(tag in lower for tag in ('_(vocals)_','_(instrumental)_','_(other)_')):continue
                wanted=('_(instrumental)_','_(other)_') if 'melband_roformer_inst_v2' in lower else ('_(vocals)_',)
                if not any(tag in lower for tag in wanted):continue
                stat=source.stat();signature=(stat.st_size,stat.st_mtime_ns)
                if seen.get(name)==signature:continue
                if stable.get(name)!=signature:stable[name]=signature;continue
                try:
                    info=sf.info(source)
                    expected=sf.info(folder/'source.wav')
                    if info.frames!=expected.frames:continue
                    shutil.copy2(source,destination/name)
                except (OSError,RuntimeError):continue
                seen[name]=signature
                print('CAPTURED',name,flush=True)
        (WORK/'capture-index.json').write_text(json.dumps({'files':list(seen),'jobs':jobs},ensure_ascii=False,indent=2),encoding='utf8')
        if not any(job['status'] in ('processing','queued','cancelling') for job in jobs):
            print('EZO JOB FINISHED',flush=True);return
        time.sleep(2)


if __name__=='__main__':main()
