"""Verify the deployed preset through frontend -> API -> real separator pipeline."""
import json
from pathlib import Path
import sys
import time
import urllib.request
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import service_control


def request(path,data=None):
    body=json.dumps(data).encode() if data is not None else None
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:3000'+path,data=body,
            headers={'Content-Type':'application/json'}),timeout=20) as r:return json.load(r)


def main():
    preset=json.loads((ROOT/'frontend/src/lib/atlas-studio-v2-preset.json').read_text(encoding='utf8'))
    source=ROOT/'cache/ezo_karaoke/Ezo_LiveCheck_80_83.wav'
    assert source.exists()
    before=request('/api/service')
    assert before['revision']==service_control.revision()
    task=request('/ensemble',{'audio_path':str(source),'models':preset['models'],'out_format':'wav',
        'params':{'ensemble_profile':'atlas_studio_v2'}})['task_id']
    last=None
    for _ in range(240):
        status=request('/status/'+task)
        if status['message']!=last:print(status['status'],status.get('progress'),status['message'],flush=True);last=status['message']
        if status['status']=='completed':break
        if status['status'] in ('error','failed','cancelled'):raise RuntimeError(str(status))
        time.sleep(1)
    else:raise RuntimeError('Live test timed out; no service restart attempted')
    arrays=[sf.read(ROOT/'outputs'/name,always_2d=True)[0] for name in status['stems']]
    original,rate=sf.read(source,always_2d=True)
    assert len(arrays)==2 and all(x.shape==original.shape and np.isfinite(x).all() for x in arrays)
    error=float(np.max(np.abs(sum(arrays)-original)))
    assert error<1e-6 and request('/api/service')['pid']==before['pid']
    result={'passed':True,'revision':preset['revision'],'task_id':task,'sum_max_abs_error':error,
        'backend_pid_unchanged':True,'frames':len(original),'stems':status['stems']}
    path=ROOT/'docs/atlas-studio-v2-refined-check.json';report=json.loads(path.read_text(encoding='utf8'))
    report['runtime_live_check']=result;path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('LIVE CHECK PASSED',json.dumps(result),flush=True)


if __name__=='__main__':main()
