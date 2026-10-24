"""Two reproducible instrumental recipes; no fallback to an unrelated average."""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

PRESETS=json.loads((Path(__file__).parent/'frontend/src/lib/comparison-presets.json').read_text(encoding='utf8'))


def attach_sw_vocal_pair(instance):
    """The installed runner writes only a primary/secondary pair, even for six heads."""
    original=instance.demix
    instance.primary_stem_name='vocals'
    instance.secondary_stem_name='instrumental'
    def demix(mix):
        sources=original(mix)
        if not isinstance(sources,dict) or 'vocals' not in sources:
            raise ValueError('SW vokal kanalı bulunamadı')
        vocal=sources['vocals']
        return {'vocals':vocal,'instrumental':mix-vocal}
    instance.demix=demix


def validate_models(models, profile, out_format='wav'):
    if profile not in PRESETS:
        raise ValueError('Bilinmeyen karşılaştırma preseti')
    if models != PRESETS[profile]['models']:
        raise ValueError('Preset modelleri değiştirilmiş. Hazır ayarı yeniden uygulayın.')
    if out_format not in ('wav','flac'):
        raise ValueError('Karşılaştırma presetleri WAV veya FLAC gerektirir.')


def stem_kind(path):
    for tag in reversed(re.findall(r'\(([^)]+)\)',Path(path).stem.lower())):
        if tag in ('vocals','vocal'):return 'vocal'
        if tag in ('instrumental','instrument','other'):return tag
    raise ValueError('Model çıktısının kanal etiketi tanınmadı: '+Path(path).name)


def max_spectrum(waves):
    """UVR Max Spec: choose the complex bin with greatest magnitude, including its phase."""
    import librosa
    import numpy as np
    result=None
    for wave in waves:
        if wave.ndim!=2 or wave.shape[1]!=2 or not np.isfinite(wave).all():
            raise ValueError('Geçersiz stereo ses')
        spec=librosa.stft(wave.T,n_fft=2048,hop_length=1024)
        if result is None:result=spec
        else:
            if result.shape!=spec.shape:raise ValueError('Ensemble süreleri uyuşmuyor')
            result=np.where(np.abs(spec)>=np.abs(result),spec,result)
    if result is None:raise ValueError('Model çıktısı yok')
    return librosa.istft(result,hop_length=1024,length=len(wave)).T


def run(core, source, models, out_format, output_dir, progress, profile):
    import numpy as np
    import soundfile as sf
    from task_cancellation import task_cancellation
    validate_models(models,profile,out_format)
    if profile == 'clean_music_restore':
        from instrument_recovery import run_recovery
        return run_recovery(core,source,out_format,output_dir,progress)
    if profile == 'clean_music':
        return run_clean_music(core,source,out_format,output_dir,progress)
    preset=PRESETS[profile]
    output_dir=Path(output_dir)
    token=uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix=preset['prefix']+'_',dir=output_dir) as work:
        prepared=Path(work)/'source.wav'
        command=['ffmpeg','-y','-v','error','-i',str(source),'-ac','2','-ar','44100','-c:a','pcm_f32le',str(prepared)]
        result=subprocess.run(command,capture_output=True)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-1500:])
        mixture,rate=sf.read(prepared,dtype='float32',always_2d=True)
        estimates=[]
        for index,model in enumerate(models):
            task_cancellation.checkpoint()
            progress(index*.45,preset['name']+f' · Model {index+1}/2')
            folder=Path(work)/str(index);folder.mkdir()
            files=core.roformer_separator(str(prepared),model['model_key'],'wav',256,False,8,1,1,0,'',
                work_dir=str(folder),float_output=True,
                progress_callback=lambda p,m,index=index:progress((index+p)*.45,m))
            candidates={}
            for path in files:
                try:kind=stem_kind(path)
                except ValueError:continue
                if kind in candidates:raise ValueError('Model aynı kanalı iki kez üretti')
                candidates[kind]=path
            # SW has six stems. Its "other" excludes bass/drums/piano/guitar.
            # Obtain its complete accompaniment by subtracting vocals from the mixture.
            is_sw=model['model_key']=='BS Roformer SW 6 Stem by jarredou'
            chosen=candidates.get('vocal') if is_sw else candidates.get('instrumental') or candidates.get('instrument') or candidates.get('other')
            if not chosen:raise ValueError('Beklenen model kanalı bulunamadı')
            wave,sr=sf.read(chosen,dtype='float32',always_2d=True)
            if sr!=rate or wave.shape!=mixture.shape or not np.isfinite(wave).all():
                raise ValueError('Model çıktısı kaynak süre veya kanal yapısıyla uyuşmuyor')
            estimates.append(mixture-wave if is_sw else wave)
            core.clear_gpu_and_ram_cache()
        progress(.93,'Max FFT / Max Spec ile enstrümanlar birleştiriliyor…')
        task_cancellation.checkpoint()
        instrumental=max_spectrum(estimates)
        vocal=mixture-instrumental
        # A shared gain preserves both stems' relative level when encoding FLAC.
        peak=max(float(np.abs(instrumental).max()),float(np.abs(vocal).max()))
        gain=min(1.,.999/peak) if out_format=='flac' and peak else 1.
        outputs=[]
        with task_cancellation.commit():
            try:
                for label,wave in [('Vocals',vocal),('Instrumental',instrumental)]:
                    target=output_dir/f"{preset['prefix']}_{label}_{token}.{out_format}"
                    sf.write(target,wave*gain,rate,subtype='FLOAT' if out_format=='wav' else 'PCM_24')
                    outputs.append(str(target))
            except BaseException:
                for path in outputs:Path(path).unlink(missing_ok=True)
                raise
        return outputs


def median_spectrum(waves):
    """Select the middle-magnitude complex bin; preserve its own phase."""
    import librosa
    import numpy as np
    if len(waves)!=3 or any(w.shape!=waves[0].shape or w.ndim!=2 or w.shape[1]!=2 or not np.isfinite(w).all() for w in waves):
        raise ValueError('Clean Music üç eş süreli stereo altyapı gerektirir')
    spectra=np.stack([librosa.stft(w.T,n_fft=2048,hop_length=1024) for w in waves])
    indices=np.argsort(np.abs(spectra),axis=0)[1]
    selected=np.take_along_axis(spectra,indices[None],axis=0)[0]
    return librosa.istft(selected,hop_length=1024,length=len(waves[0])).T


def run_clean_music(core,source,out_format,output_dir,progress):
    import numpy as np
    import soundfile as sf
    from atlas_studio import PRESET, run_atlas_studio
    from task_cancellation import task_cancellation
    root=Path(output_dir)
    root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='CleanMusic_',dir=root) as work:
        prepared=Path(work)/'source.wav'
        decoded=subprocess.run(['ffmpeg','-y','-v','error','-i',str(source),'-ac','2','-ar','44100','-c:a','pcm_f32le',str(prepared)],capture_output=True)
        if decoded.returncode:raise RuntimeError(decoded.stderr.decode(errors='replace')[-1500:])
        mixture,rate=sf.read(prepared,dtype='float32',always_2d=True)
        estimates=[]
        stages=[('lale_instrument',2),('sedef_clean',2),('atlas_studio',3)]
        completed=0
        for profile,count in stages:
            task_cancellation.checkpoint()
            folder=Path(work)/profile;folder.mkdir()
            def report(p,m,offset=completed,count=count):
                task_cancellation.checkpoint()
                progress(.9*(offset+count*p)/7,'Clean Music · '+m)
            if profile=='atlas_studio':
                models=[{k:m[k] for k in ('model_type','model_key')} for m in PRESET['models']]
                files=run_atlas_studio(core,prepared,models,'wav',folder,report,preset=PRESET)
            else:
                files=run(core,prepared,PRESETS[profile]['models'],'wav',folder,report,profile)
            paths=[p for p in files if 'Instrumental' in Path(p).name]
            if len(paths)!=1:raise ValueError('Clean Music altyapı çıktısı bulunamadı')
            wave,sr=sf.read(paths[0],dtype='float32',always_2d=True)
            if sr!=rate or wave.shape!=mixture.shape or not np.isfinite(wave).all():raise ValueError('Clean Music kanal süreleri uyuşmuyor')
            estimates.append(wave)
            completed+=count
        progress(.93,'Clean Music · Üç altyapı spektral ortanca ile birleştiriliyor…')
        task_cancellation.checkpoint()
        instrumental=median_spectrum(estimates)
        vocal=mixture-instrumental
        peak=max(float(np.abs(instrumental).max()),float(np.abs(vocal).max()))
        gain=min(1.,.999/peak) if out_format=='flac' and peak else 1.
        token=uuid.uuid4().hex[:12]
        outputs=[]
        with task_cancellation.commit():
            try:
                for label,wave in [('Vocals',vocal),('Instrumental',instrumental)]:
                    path=root/f'CleanMusic_{label}_{token}.{out_format}'
                    outputs.append(str(path))
                    sf.write(path,wave*gain,rate,subtype='FLOAT' if out_format=='wav' else 'PCM_24')
            except BaseException:
                for path in outputs:Path(path).unlink(missing_ok=True)
                raise
        return outputs
