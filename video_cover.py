"""Optional MP4 cover art without adding frames to the karaoke timeline."""
import base64
import io
import os
from pathlib import Path
import subprocess
import tempfile
from PIL import Image, ImageOps


def cover_bytes(data):
    if not data:return None
    try:
        header,payload=data.split(',',1)
        if header not in ('data:image/jpeg;base64','data:image/png;base64','data:image/webp;base64'):
            raise ValueError()
        raw=base64.b64decode(payload,validate=True)
        if len(raw)>4*1024*1024:raise ValueError()
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ('JPEG','PNG','WEBP') or image.width*image.height>40_000_000:raise ValueError()
            image=ImageOps.exif_transpose(image).convert('RGBA')
            image.thumbnail((1920,1920))
            background=Image.new('RGB',image.size,(9,9,11));background.paste(image,mask=image.getchannel('A'))
            output=io.BytesIO();background.save(output,format='JPEG',quality=92)
            return output.getvalue()
    except Exception as exc:
        raise ValueError('Kapak görseli açılamadı. Geçerli bir JPG, PNG veya WebP seçin.') from exc


def attach_cover(video,data):
    image=cover_bytes(data)
    if image is None:return
    video=Path(video).resolve()
    with tempfile.TemporaryDirectory(prefix='karaoke-cover-',dir=video.parent) as folder:
        cover=Path(folder)/'cover.jpg';cover.write_bytes(image)
        result=Path(folder)/'covered.mp4'
        cmd=['ffmpeg','-y','-i',str(video),'-i',str(cover),'-map','0:v:0','-map','0:a?',
             '-map','1:v:0','-map_metadata','0','-c','copy','-c:v:1','mjpeg',
             '-disposition:v:0','default','-disposition:v:1','attached_pic','-movflags','+faststart',str(result)]
        proc=subprocess.run(cmd,capture_output=True,text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if proc.returncode:raise RuntimeError('Video kapağı eklenemedi: '+proc.stderr[-400:])
        os.replace(result,video)
