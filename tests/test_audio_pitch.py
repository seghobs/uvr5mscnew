import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from audio_pitch import validate_pitch_parameters, render_pitch_audio


class PitchTests(unittest.TestCase):
    def test_tone_frequency_and_duration_are_independent(self):
        rate=24000
        frames=rate*3
        frequency=261.625565  # C4
        signal=.2*np.sin(2*np.pi*frequency*np.arange(frames)/rate)
        with tempfile.TemporaryDirectory() as work:
            source=Path(work)/'source.wav';target=Path(work)/'preview.wav'
            sf.write(source,signal,rate)
            for pitch,tempo in [(p,1) for p in range(-12,13)]+[(11,.55),(9,2),(0,.55)]:
                with self.subTest(pitch=pitch,tempo=tempo):
                    render_pitch_audio(source,target,pitch,tempo)
                    samples,sr=sf.read(target)
                    self.assertEqual(sr,rate)
                    self.assertEqual(len(samples),round(frames/tempo))
                    middle=samples[len(samples)//4:len(samples)*3//4]
                    spectrum=np.abs(np.fft.rfft(middle*np.hanning(len(middle))))
                    measured=np.fft.rfftfreq(len(middle),1/sr)[spectrum.argmax()]
                    expected=frequency*2**(pitch/12)
                    self.assertLess(abs(measured-expected),2.)

    def test_invalid_parameters_rejected(self):
        for pitch,tempo in [(13,1),(0,0),(float('nan'),1),(0,float('inf'))]:
            with self.assertRaises(ValueError):validate_pitch_parameters(44100,44100,pitch,tempo)

    def test_stereo_transients_and_unity_bypass(self):
        rate = 24000
        signal = np.zeros(rate * 5, dtype=np.float32)
        rng = np.random.default_rng(7)
        for second in (1, 2, 3, 4):
            signal[second*rate:second*rate+480] = rng.uniform(-.2, .2, 480) * np.hanning(480)
        stereo = np.column_stack([signal, signal])
        with tempfile.TemporaryDirectory() as work:
            source = Path(work)/'source.wav'
            target = Path(work)/'preview.wav'
            sf.write(source, stereo, rate, subtype='FLOAT')
            for pitch in (-12, -7, 0, 7, 12):
                with self.subTest(pitch=pitch):
                    render_pitch_audio(source,target,pitch)
                    output, _ = sf.read(target, dtype='float32', always_2d=True)
                    self.assertEqual(output.shape, stereo.shape)
                    np.testing.assert_allclose(output[:,0],output[:,1],atol=1e-6)
                    if pitch == 0:
                        np.testing.assert_array_equal(output,stereo)
                    for second in (1,2,3,4):
                        start = int((second-.1)*rate)
                        segment = output[start:int((second+.1)*rate),0]
                        peak_time = (start+np.argmax(np.abs(segment)))/rate
                        self.assertLess(abs(peak_time-(second+.01)),.04)

    def test_lossless_export_precision(self):
        with tempfile.TemporaryDirectory() as work:
            source=Path(work)/'source.wav'
            target=Path(work)/'export.flac'
            sf.write(source,.25*np.sin(np.arange(44100)*2*np.pi*440/44100),44100,subtype='FLOAT')
            render_pitch_audio(source,target,9)
            info=sf.info(target)
            self.assertEqual(info.frames,44100)
            self.assertEqual(info.subtype,'PCM_24')


if __name__=='__main__':unittest.main()
