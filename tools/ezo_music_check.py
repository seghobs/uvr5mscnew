"""Restore the cached three-pass Ezo blend; quantify changes, not true fidelity."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import numpy as np
import soundfile as sf
from scipy.signal import welch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from atlas_studio import PRESET_V2


def main():
    folder=ROOT/'outputs/Ezo_Karaoke_Gelistirme'
    baseline=folder/'Ezo_V2_SinglePass_Baseline.wav'
    previous=folder/'Ezo_Strict_1.0_Instrumental.wav'
    target=folder/'Ezo_V2_Music_Instrumental.wav'
    # This cached baseline used exactly these weights, with no extra subtraction.
    old=json.loads((ROOT/'docs/atlas-studio-v2-ezo-check.json').read_text(encoding='utf8'))
    assert old['selected_preset']['models']==PRESET_V2['models']
    assert PRESET_V2['inference_passes']==[{'transform':'identity','weight':1.}]
    assert 'residual_cleanup' not in PRESET_V2
    a=sf.info(baseline);b=sf.info(previous)
    assert (a.frames,a.channels,a.samplerate)==(b.frames,b.channels,b.samplerate)
    bands={'sub_bass_20_60':(20,60),'bass_60_250':(60,250),
           'low_mid_250_1000':(250,1000),'mid_1000_4000':(1000,4000),
           'presence_4000_10000':(4000,10000),'air_10000_20000':(10000,20000)}
    energy=np.zeros(3);spectra=None;peak=0.
    with sf.SoundFile(baseline) as first,sf.SoundFile(previous) as second:
        while True:
            music=first.read(262144,dtype='float64',always_2d=True)
            if not len(music):break
            strict=second.read(len(music),dtype='float64',always_2d=True)
            assert np.isfinite(music).all() and np.isfinite(strict).all()
            difference=music-strict
            waves=(music,strict,difference)
            energy+=np.array([np.sum(x*x) for x in waves])
            peak=max(peak,float(np.max(np.abs(music))))
            if len(music)>=8192:
                values=[]
                for x in waves:
                    frequencies,power=welch(x,fs=a.samplerate,nperseg=8192,axis=0)
                    values.append(power.sum(axis=1)*len(x))
                if spectra is None:spectra=np.array(values)
                else:spectra+=values
    comparison={}
    for name,(lo,hi) in bands.items():
        mask=(frequencies>=lo)&(frequencies<hi)
        powers=spectra[:,mask].sum(axis=1)
        comparison[name]={'previous_strict_to_music_power_db':float(10*np.log10(max(powers[1],1e-30)/max(powers[0],1e-30))),
            'changed_component_energy_relative_to_music':float(powers[2]/max(powers[0],1e-30))}
    shutil.copy2(baseline,target)
    with sf.SoundFile(target) as source:
        source.seek(80*a.samplerate)
        sf.write(folder/'Ezo_V2_Music_80_96.wav',source.read(16*a.samplerate),a.samplerate,subtype='FLOAT')
    report={'selected_preset':PRESET_V2,'distinct_separation_models':3,'full_inference_passes':3,
        'secondary_vocal_subtraction':False,'isolated_reference_stems_available':False,
        'zero_leakage_verified':False,'true_instrumental_sdr_db':None,
        'true_music_fidelity_improvement_verified':False,'perceptual_listening_performed':False,
        'duration_seconds':a.duration,'sample_rate':a.samplerate,'channels':a.channels,
        'output_peak':peak,'changed_component_energy_relative_to_music':float(energy[2]/energy[0]),
        'band_comparison':comparison,'output':str(target),
        'baseline_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),
        'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'interpretation':'The new output exactly restores the cached single-pass blend before secondary vocal subtraction. Changed energy includes unknown amounts of music and voice; band energy does not measure instrument fidelity or isolated drum/bass retention. Primary separation may still remove music or leave voice. Historical strict-cleanup reports do not describe this revision.'}
    (ROOT/'docs/atlas-studio-v2-music-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
