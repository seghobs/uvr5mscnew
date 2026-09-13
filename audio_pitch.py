"""Duration-preserving musical transposition with coupled stereo processing."""
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def render_pitch_audio(source, target, semitones, tempo=1.0, cancel_event=None, progress=None):
    """Two-pass R3 processing; always work from source, with floating-point intermediates."""
    import soundfile as sf
    info = sf.info(str(source))
    validate_pitch_parameters(info.samplerate, info.frames, semitones, tempo)  # validate
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    def report(value,message):
        if progress: progress(value,message)
    def run(command):
        from audio_jobs import JobCancelled
        if cancel_event is not None and cancel_event.is_set(): raise JobCancelled()
        with tempfile.TemporaryFile() as errors:
            process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=errors,creationflags=flags)
            deadline=time.monotonic()+600
            try:
                while process.poll() is None:
                    if cancel_event is not None and cancel_event.is_set(): raise JobCancelled()
                    if time.monotonic()>deadline: raise TimeoutError('Ses işlemi zaman aşımına uğradı.')
                    time.sleep(.05)
                if process.returncode:
                    errors.seek(0)
                    raise RuntimeError(errors.read().decode('utf-8',errors='replace')[-1500:])
            finally:
                if process.poll() is None: process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill();process.wait()
    report(.05,'Kaynak ses okunuyor')

    with tempfile.TemporaryDirectory(prefix='uvr_transpose_') as work:
        processed = Path(source)
        if semitones != 0 or tempo != 1:
            bundled = Path(__file__).parent/'tools/rubberband/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
            executable = str(bundled) if os.name == 'nt' and bundled.is_file() else shutil.which('rubberband')
            if not executable:
                raise RuntimeError('Yüksek kaliteli transpoze motoru (Rubber Band) bulunamadı.')
            decoded = Path(work)/'input.wav'
            processed = Path(work)/'processed.wav'
            run(['ffmpeg','-y','-v','error','-i',str(source),'-vn','-c:a','pcm_f32le',str(decoded)])
            report(.15,'Yüksek kaliteli ton işleniyor')
            run([executable,'--fine','--formant','--centre-focus','--quiet',
                 '--pitch',str(semitones),'--tempo',str(tempo),str(decoded),str(processed)])
        report(.9,'Ses dosyası hazırlanıyor')
        count = round(info.frames/tempo)
        command = ['ffmpeg','-y','-v','error','-i',str(processed),'-vn','-af',
                   f'apad=whole_len={count},atrim=end_sample={count}']
        if Path(target).suffix.lower() == '.wav':
            command += ['-c:a','pcm_f32le']
        elif Path(target).suffix.lower() == '.flac':
            command += ['-c:a','flac','-sample_fmt','s32']
        run(command+[str(target)])


def validate_pitch_parameters(sample_rate, frames, semitones, tempo=1.0):
    if (not math.isfinite(semitones) or not -12 <= semitones <= 12
            or not math.isfinite(tempo) or not .5 <= tempo <= 2
            or sample_rate <= 0 or frames < 0):
        raise ValueError('Invalid pitch, tempo or source dimensions')
