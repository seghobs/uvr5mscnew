"""Fixed, small reference pilot; never fit transforms or weights to test audio."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from local_runtime import configure_local_runtime
configure_local_runtime()
import numpy as np
import soundfile as sf
import core
from atlas_studio import PRESET, PRESET_V2, transform_audio, run_model_estimate, combine
from tools.atlas_benchmark import metrics


def main():
    work=ROOT/'cache/atlas_benchmark'
    destination=ROOT/'cache/atlas_conservative';destination.mkdir(exist_ok=True)
    manifest=json.loads((work/'manifest.json').read_text(encoding='utf8'))
    selected=[track for split in ('train','test')
              for track in [t for t in manifest['tracks'] if t['split']==split][:2]]
    rows=[]
    for track in selected:
        folder=work/'estimates'/track['id'];out=destination/track['id'];out.mkdir(exist_ok=True)
        with np.load(folder/'reference.npz') as ref:
            source=ref['source'];headroom=float(ref['headroom'])
            references={key:ref[key] for key in ('vocal','instrumental')}
        prepared,rate=sf.read(folder/'input.wav',dtype='float64',always_2d=True)
        estimates=[];baseline=[]
        for index,(model,candidate_index) in enumerate(zip(PRESET['models'],(0,2,4))):
            candidate=np.load(folder/f'candidate_{candidate_index}.npy').astype('float64')
            original=source-candidate if model['estimate']=='inst' else candidate
            baseline.append(original)
            averaged=.5*original
            for transform in ('swap_channels','invert_polarity'):
                cache=out/f'{index}_{transform}.npy'
                if cache.exists():estimate=np.load(cache)
                else:
                    audio=out/f'{transform}.wav'
                    sf.write(audio,transform_audio(prepared,transform),rate,subtype='FLOAT')
                    print('INFER',track['split'],track['name'],index+1,transform,flush=True)
                    estimate=run_model_estimate(core,audio,model,out,rate,len(prepared),len(source),headroom,lambda p,m:None)
                    np.save(cache,estimate)
                averaged+=.25*transform_audio(estimate,transform)
            estimates.append(averaged)
        systems={}
        for name,est in [('atlas_studio',baseline),('conservative_tta',estimates)]:
            vocal,inst=combine(source,est,PRESET)
            systems[name]={key:metrics(references[key],wave) for key,wave in [('vocal',vocal),('instrumental',inst)]}
        rows.append({'name':track['name'],'split':track['split'],'systems':systems})
        report={'preset':PRESET_V2,'scope':'Four seven-second excerpts; fixed weights/transforms. Existing reference cache, no fitting. This is not a perceptual or zero-artifact guarantee.','tracks':rows}
        report['summary']={split:{name:{stem:{metric:float(np.mean([row['systems'][name][stem][metric] for row in rows if row['split']==split]))
            for metric in ('sdr_db','si_sdr_db','spectral_deficit','spectral_excess')} for stem in references}
            for name in systems} for split in ('train','test') if any(row['split']==split for row in rows)}
        (ROOT/'docs/atlas-studio-v2-conservative-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print('SCORED',track['name'],json.dumps(systems,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
