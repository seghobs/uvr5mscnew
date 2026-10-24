"""Conditional drum/bass gain diagnostics using actual cached reference stems."""
import json
from pathlib import Path
import subprocess
import sys
import os
import numpy as np
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.atlas_benchmark import load
from atlas_band_ensemble import combine_frequency


def main():
    fit=json.loads((ROOT/'cache/atlas_music_fit/report.json').read_text(encoding='utf8'))
    tracks=json.loads((ROOT/'cache/atlas_benchmark/manifest.json').read_text(encoding='utf8'))['tracks'];rows=[]
    for track in tracks:
        if track['split']!='test':continue
        ref,c=load(track);c=c[[0,2,4]];stems=[]
        for stream in (1,2):
            result=subprocess.run(['ffmpeg','-v','error','-i',str(ROOT/'cache/atlas_benchmark'/track['file']),'-map',f'0:a:{stream}',
                '-ac','2','-ar','44100','-f','f32le','-'],check=True,capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            stems.append(np.frombuffer(result.stdout,dtype='<f4').reshape(-1,2).astype('float64'))
        drums,bass=stems;basis=np.stack([drums.ravel(),bass.ravel(),(ref['instrumental']-drums-bass).ravel(),ref['vocal'].ravel()])
        systems={}
        for key,weights in [('v1',[.5,.25,.25]),('previous_v2',[.55,.25,.2]),('refined',None)]:
            if weights is None:_,inst=combine_frequency(ref['source'],c,fit['frequency_weights'])
            else:inst=ref['source']-np.tensordot(weights,c,axes=(0,0))
            gains=np.linalg.lstsq(basis.T,inst.ravel(),rcond=None)[0]
            systems[key]={'drum_gain':float(gains[0]),'bass_gain':float(gains[1]),
                'drum_gain_squared_error':float((gains[0]-1)**2),'bass_gain_squared_error':float((gains[1]-1)**2)}
        rows.append({'name':track['name'],'systems':systems})
    summary={key:{metric:float(np.mean([row['systems'][key][metric] for row in rows])) for metric in rows[0]['systems'][key]}
             for key in rows[0]['systems']}
    report={'scope':'Eight previously reused local evaluation excerpts with original reference drum and bass streams. Conditional linear gain is a limited retention proxy, not isolated output SDR or listening quality. Ezo lacks these reference stems.',
        'frequency_weights':fit['frequency_weights'],'summary':summary,'rows':rows}
    (ROOT/'cache/atlas_music_fit/component-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
