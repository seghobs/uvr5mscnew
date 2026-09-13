"""Four bounded local attempts; return pasted rows even when recognition fails."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from karaoke_anchored import anchor_transcript_rows

ATTEMPTS=4
ATTEMPT_SECONDS=15


def synchronize(path,text,language='tr',progress=lambda *args:None):
    best,report=anchor_transcript_rows(text,[])
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='paste-sync-') as folder:
        request=Path(folder)/'request.json';output=Path(folder)/'result.json'
        for attempt in range(ATTEMPTS):
            progress(attempt/ATTEMPTS,f'Senkron denemesi {attempt+1}/4 · en fazla 15 saniye')
            request.write_text(json.dumps({'path':str(Path(path).resolve()),'text':text,'language':language,'attempt':attempt}),encoding='utf8')
            output.unlink(missing_ok=True)
            try:
                subprocess.run([sys.executable,str(root/'paste_sync.py'),'--worker',str(request),str(output)],
                    cwd=root,timeout=ATTEMPT_SECONDS,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                data=json.loads(output.read_text('utf8'))
                rows,candidate_report=anchor_transcript_rows(text,data)
                if candidate_report['aligned']>report['aligned']:best,report=rows,candidate_report
                if not report['pending']:break
            except (subprocess.TimeoutExpired,subprocess.CalledProcessError,OSError,ValueError):
                pass
    report.update(attempts=attempt+1,mode='line_by_line')
    return best,report


def worker(request_path,output_path):
    from local_runtime import configure_local_runtime
    configure_local_runtime()
    root=Path(__file__).resolve().parent
    # Same DLL search paths as the normal backend, also when started without start.bat.
    handles=[]
    if hasattr(os,'add_dll_directory'):
        for folder in ('env/Library/bin','env/Lib/site-packages/torch/lib'):
            location=root/folder
            if location.is_dir():handles.append(os.add_dll_directory(str(location)))
    import ctranslate2
    from faster_whisper import WhisperModel
    req=json.loads(Path(request_path).read_text('utf8'))
    models=('large-v3-turbo','large-v3')
    selected=root/'models/whisper'/models[req['attempt']%2]
    if not (selected/'model.bin').exists():
        selected=root/'models/whisper'/models[1-req['attempt']%2]
    if not (selected/'model.bin').exists():raise ValueError('Yerel Whisper modeli bulunamadı.')
    device='cuda' if ctranslate2.get_cuda_device_count() else 'cpu'
    model=WhisperModel(str(selected),device=device,compute_type='float16' if device=='cuda' else 'int8',local_files_only=True)
    language=req['language']
    # Do not force Turkish for pasted Kurdish words or auto-detection requests.
    if language in (None,'','auto','none') or any(c in req['text'].lower() for c in 'êîû'):language=None
    decoded,_=model.transcribe(req['path'],language=language,word_timestamps=True,
        vad_filter=True,condition_on_previous_text=False,temperature=0.,beam_size=5 if req['attempt']<2 else 8)
    rows=[{'words':[{'word':w.word.strip(),'start':w.start,'end':w.end,'probability':w.probability,
                    'timing_source':'whisper','needs_review':True} for w in seg.words or []
                   if w.end>w.start and w.probability>=.6]} for seg in decoded if seg.no_speech_prob<=.6]
    Path(output_path).write_text(json.dumps(rows,ensure_ascii=False),encoding='utf8')


if __name__=='__main__' and len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3])
