import base64
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import av
from PIL import Image
from video_cover import attach_cover,cover_bytes
from local_projects import ProjectStore


class CoverTests(unittest.TestCase):
    def cover(self):
        data=io.BytesIO();Image.new('RGB',(160,90),'red').save(data,format='PNG')
        return 'data:image/png;base64,'+base64.b64encode(data.getvalue()).decode()

    def test_optional_invalid_and_per_song_persistence(self):
        self.assertIsNone(cover_bytes(None))
        for value in ('data:image/svg+xml;base64,abc','data:image/png;base64,broken','file:///tmp/image.png'):
            with self.assertRaises(ValueError):cover_bytes(value)
        with tempfile.TemporaryDirectory() as folder:
            store=ProjectStore(folder)
            store.put('uvr-video-cover:a.wav',self.cover());store.put('uvr-video-cover:b.wav','other')
            self.assertNotEqual(store.path('uvr-video-cover:a.wav').parent,store.path('uvr-video-cover:b.wav').parent)
            self.assertEqual(ProjectStore(folder).get('uvr-video-cover:a.wav'),self.cover())
            store.put('uvr-video-cover:a.wav',None)
            self.assertEqual(store.get('uvr-video-cover:b.wav'),'other')

    def test_mp4_cover_keeps_audio_video_timeline_and_first_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'clip.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=160x90:r=25:d=1',
                '-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac','-shortest',str(path)],check=True)
            def probe():
                with av.open(str(path)) as container:
                    return [dict(codec_type=s.type,codec_name=s.codec_context.name,duration_ts=s.duration,
                                 time_base=str(s.time_base),disposition={'attached_pic':bool(s.disposition & av.stream.Disposition.attached_pic)})
                            for s in container.streams]
            before=probe();unchanged=path.read_bytes();attach_cover(path,None);self.assertEqual(unchanged,path.read_bytes())
            attach_cover(path,self.cover());after=probe()
            for original in before:
                actual=next(s for s in after if s['codec_type']==original['codec_type'] and not s['disposition']['attached_pic'])
                self.assertEqual(actual['duration_ts'],original['duration_ts'])
                self.assertEqual(actual['time_base'],original['time_base'])
            cover=next(s for s in after if s['disposition']['attached_pic']);self.assertEqual(cover['codec_name'],'mjpeg')
            image=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:v:0','-frames:v','1','-f','image2pipe','-c:v','png','-'])
            r,g,b=Image.open(io.BytesIO(image)).getpixel((20,20))[:3];self.assertGreater(b,200);self.assertLess(r,20)
