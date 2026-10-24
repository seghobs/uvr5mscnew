"""Transfer only residual audio into Clean Music under bounded specialist masks."""
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

import numpy as np
import soundfile as sf


def recover_instruments(mixture, baseline, targets, strength=.65):
    import librosa
    from scipy.ndimage import uniform_filter
    if not 0<=strength<=1 or not targets:
        raise ValueError('Geçersiz enstrüman geri kazanım ayarı')
    if mixture.ndim!=2 or mixture.shape[1]!=2 or any(w.shape!=mixture.shape or not np.isfinite(w).all() for w in [mixture,baseline,*targets]):
        raise ValueError('Geri kazanım sesleri eş süreli stereo olmalı')
    if strength==0:return baseline.copy()
    original=librosa.stft(mixture.T,n_fft=2048,hop_length=512)
    # MAX avoids double-counting flute inside the broader wind prediction.
    magnitude=np.maximum.reduce([np.abs(librosa.stft(w.T,n_fft=2048,hop_length=512)) for w in targets])
    reference=np.abs(original)
    mask=np.clip(magnitude/np.maximum(reference,1e-7),0,1)**2
    mask=np.where(reference>max(float(reference.max())*1e-5,1e-7),mask,0)
    mask=np.clip(uniform_filter(mask,size=(1,3,5),mode='nearest'),0,1)
    residual=librosa.stft((mixture-baseline).T,n_fft=2048,hop_length=512)
    recovered=librosa.istft(residual*mask*strength,hop_length=512,length=len(mixture)).T
    return baseline+recovered


def target_output(files,target):
    matches=[p for p in files if re.findall(r'\(([^)]+)\)',Path(p).stem.lower())[-1:]==[target]]
    if len(matches)!=1:raise ValueError(f'{target} hedef kanalı bulunamadı; geri kazanım durduruldu')
    return matches[0]


def run_recovery(core,source,out_format,output_dir,progress):
    from comparison_ensemble import PRESETS,run_clean_music
    from task_cancellation import task_cancellation
    if out_format not in ('wav','flac'):raise ValueError('Restore WAV veya FLAC gerektirir')
    preset=PRESETS['clean_music_restore']
    root=Path(output_dir);root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='CleanMusicRestore_',dir=root) as work:
        work=Path(work);prepared=work/'source.wav'
        task_cancellation.checkpoint()
        decoded=subprocess.run(['ffmpeg','-y','-v','error','-i',str(source),'-ac','2','-ar','44100','-c:a','pcm_f32le',str(prepared)],capture_output=True)
        if decoded.returncode:raise RuntimeError(decoded.stderr.decode(errors='replace')[-1500:])
        mixture,rate=sf.read(prepared,dtype='float32',always_2d=True)
        base_dir=work/'clean';base_dir.mkdir()
        files=run_clean_music(core,prepared,'wav',base_dir,lambda p,m:progress(p*.65,m))
        paths=[p for p in files if 'Instrumental' in Path(p).name]
        if len(paths)!=1:raise ValueError('Clean Music altyapısı bulunamadı')
        baseline,sr=sf.read(paths[0],dtype='float32',always_2d=True)
        if sr!=rate or baseline.shape!=mixture.shape:raise ValueError('Clean Music süresi uyuşmuyor')
        targets=[]
        from json import loads
        specs=loads((Path(__file__).parent/'assets/comparison-models.json').read_text(encoding='utf8'))
        for index,model in enumerate(preset['models'][7:]):
            task_cancellation.checkpoint()
            name=model['model_key'];target=specs[name]['target']
            folder=work/target;folder.mkdir()
            progress(.65+index*.09,'Restore · '+target+' ayrılıyor…')
            files=core.roformer_separator(str(prepared),name,'wav',256,False,8,1,1,0,'',work_dir=str(folder),float_output=True,
                progress_callback=lambda p,m,index=index:progress(.65+(index+p)*.09,'Restore · '+m))
            wave,sr=sf.read(target_output(files,target),dtype='float32',always_2d=True)
            if sr!=rate or wave.shape!=mixture.shape or not np.isfinite(wave).all():raise ValueError('Uzman model süresi veya kanalı uyuşmuyor')
            targets.append(wave)
            core.clear_gpu_and_ram_cache()
        progress(.94,'Restore · Eksik enstrümanlar kontrollü aktarılıyor…')
        task_cancellation.checkpoint()
        instrumental=recover_instruments(mixture,baseline,targets,preset['recovery_strength'])
        vocal=mixture-instrumental
        peak=max(float(np.abs(instrumental).max()),float(np.abs(vocal).max()))
        gain=min(1.,.999/peak) if out_format=='flac' and peak else 1.
        token=uuid.uuid4().hex[:12];outputs=[]
        with task_cancellation.commit():
            try:
                for label,wave in [('Vocals',vocal),('Instrumental',instrumental)]:
                    path=root/f'CleanMusicRestore_{label}_{token}.{out_format}'
                    outputs.append(str(path))
                    sf.write(path,wave*gain,rate,subtype='FLOAT' if out_format=='wav' else 'PCM_24')
            except BaseException:
                for path in outputs:Path(path).unlink(missing_ok=True)
                raise
        return outputs
