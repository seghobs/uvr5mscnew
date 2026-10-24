"""Probe a reused Bleedless model on Ezo residuals; no production changes."""
import argparse
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from local_runtime import configure_local_runtime
configure_local_runtime()
import numpy as np
import soundfile as sf
import torch
import core
from atlas_studio import PRESET,run_model_estimate


def main():
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('--start',type=float,default=80);parser.add_argument('--end',type=float,default=96);parser.add_argument('--cpu',action='store_true')
    args=parser.parse_args();work=ROOT/'cache/ezo_karaoke'/f'probe_{int(args.start)}_{"cpu" if args.cpu else "gpu"}';work.mkdir(exist_ok=True)
    if args.cpu:
        torch.set_num_threads(4);core.use_autocast=False
    wave,rate=sf.read(args.source,start=round(args.start*44100),stop=round(args.end*44100),dtype='float64',always_2d=True)
    headroom=.25/max(1.,float(np.abs(wave).max()));frames=len(wave)
    prepared=work/'residual_input.wav';sf.write(prepared,np.pad(wave*headroom,((0,max(0,16*rate-frames)),(0,0))),rate,subtype='FLOAT')
    started=time.monotonic();model=PRESET['models'][1]
    def infer():return run_model_estimate(core,prepared,model,work,rate,max(frames,16*rate),frames,headroom,lambda p,m:print(round(p*100),m,flush=True))
    if args.cpu:
        with patch.object(torch.cuda,'is_available',return_value=False):removed=infer()
    else:removed=infer()
    sf.write(work/'baseline.wav',wave,rate,subtype='FLOAT');sf.write(work/'removed.wav',removed,rate,subtype='FLOAT')
    for strength in (.5,.75,1.):sf.write(work/f'clean_{strength}.wav',wave-strength*removed,rate,subtype='FLOAT')
    report={'source':str(Path(args.source).resolve()),'start':args.start,'end':args.end,'device':'cpu' if args.cpu else 'gpu',
            'model_reused':model['model_key'],'seconds':time.monotonic()-started,
            'removed_energy_relative_to_baseline':float(np.sum(removed**2)/max(float(np.sum(wave**2)),1e-12)),
            'is_true_instrumental_loss_measurement':False}
    (work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('PROBE DONE',json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
