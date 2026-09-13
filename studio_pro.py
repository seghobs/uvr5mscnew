"""Opt-in specialist ensemble. Legacy presets keep their existing pipeline."""
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

PRESET = json.loads((Path(__file__).parent / 'frontend/src/lib/studio-pro-preset.json').read_text(encoding='utf8'))


def validate_models(models):
    expected = [(m['model_type'],m['model_key']) for m in PRESET['models']]
    actual = [(m.get('model_type'),m.get('model_key')) for m in models]
    if actual != expected:
        raise ValueError('Studio Pro model listesi değişmiş. Preseti yeniden uygulayın.')


def classify_stem(path):
    # Inspect the final stem tag, not a source filename containing "vocals".
    import re
    tags = re.findall(r'\(([^)]+)\)', Path(path).stem.lower())
    for tag in reversed(tags):
        if tag in ('instrumental','other','no_vocals','no vocals','accompaniment'): return 'inst'
        if tag in ('vocals','vocal'): return 'vocal'
    raise ValueError(f'Stem türü belirlenemedi: {Path(path).name}')


def merge_command(files, weights, target, frames):
    if len(files) != len(weights) or not files or any(w <= 0 for w in weights):
        raise ValueError('Geçersiz ensemble ağırlıkları')
    args = ['ffmpeg','-y','-v','error']
    for file in files: args += ['-i',str(file)]
    tags = ''.join(f'[{i}:a]' for i in range(len(files)))
    weights_text = ' '.join(str(w) for w in weights)
    graph = f"{tags}amix=inputs={len(files)}:weights='{weights_text}':normalize=1:duration=longest,apad=whole_len={frames},atrim=end_sample={frames}[out]"
    encoding = ['-b:a','320k'] if Path(target).suffix.lower()=='.mp3' else []
    return args + ['-filter_complex',graph,'-map','[out]','-ar','44100'] + encoding + [str(target)]


def run_studio_pro(core, source, models, out_format, output_dir, progress):
    import soundfile as sf
    validate_models(models)
    output_dir = Path(output_dir)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    def execute(args):
        result = subprocess.run(args,capture_output=True,text=True,creationflags=flags)
        if result.returncode: raise RuntimeError(result.stderr[-1500:])
    token = uuid.uuid4().hex[:12]
    # Decode once to a shared lossless timebase; no repeated lossy compression.
    with tempfile.TemporaryDirectory(prefix='studio_pro_',dir=output_dir) as work:
        prepared = Path(work) / f'studio_pro_{token}.wav'
        execute(['ffmpeg','-y','-v','error','-i',str(source),'-ac','2','-ar','44100','-c:a','pcm_f32le',str(prepared)])
        frames = sf.info(prepared).frames
        # Inst V2's native 11-second context cannot handle shorter arrays in
        # the installed separator. Pad only the input, trim final stems back.
        processing_frames = max(frames,16*44100)
        if frames < processing_frames:
            import numpy as np
            wave,rate = sf.read(prepared,dtype='float32',always_2d=True)
            sf.write(prepared,np.pad(wave,((0,processing_frames-frames),(0,0))),rate,subtype='FLOAT')
        stems = {'vocal':[], 'inst':[]}
        for index, model in enumerate(models):
            progress(index/4*.9, f"Studio Pro {index+1}/4: {model['model_key']}")
            separator = core.roformer_separator if model['model_type']=='roformer' else core.mdxc_separator
            # Model-native context, overlap 8, sequential batch 1. No gain-up
            # of quiet leakage and no unrelated VR-only switches.
            files = separator(str(prepared),model['model_key'],'flac',256,False,8,1,1.0,0.0,'',
                              progress_callback=lambda p,m: progress((index+p)/4*.9,m))
            pair = {}
            for file in files:
                kind = classify_stem(file)
                if kind in pair: raise ValueError('Bir model aynı stem türünü iki kez üretti')
                info = sf.info(file)
                if info.samplerate != 44100 or info.channels != 2 or abs(info.frames-processing_frames)>44:
                    raise ValueError('Model çıktısının süresi veya kanal yapısı kaynakla uyuşmuyor')
                pair[kind] = file
            if set(pair) != {'vocal','inst'}:
                raise ValueError('Model vokal ve enstrümanı birlikte üretmedi')
            for kind in stems: stems[kind].append(pair[kind])
            core.clear_gpu_and_ram_cache()
        progress(.94,'Vokal ve enstrüman uzman ağırlıklarıyla birleştiriliyor')
        outputs = []
        for kind,label in [('vocal','Vocals'),('inst','Instrumental')]:
            target = output_dir / f'StudioPro_{label}_{token}.{out_format}'
            execute(merge_command(stems[kind],[m[f'{kind}_weight'] for m in PRESET['models']],target,frames))
            outputs.append(str(target))
        return outputs
