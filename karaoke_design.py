"""Shared artwork for preview and final karaoke composition."""
from pathlib import Path
import os
import uuid
import math
import re


def prepare_word_geometry(segments, width, height, baseline, font_size):
    """Measure the actual libass glyphs, not a different font engine's widths."""
    import hashlib,json,subprocess,tempfile,shutil
    import numpy as np
    from PIL import Image,ImageFont
    from karaoke_timing import ass_time,escape_ass
    root=Path(__file__).resolve().parent;cache=root/'cache'/'ass_word_geometry';cache.mkdir(parents=True,exist_ok=True)
    font_path=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/segoeuib.ttf'
    if not font_path.is_file():return [None for _ in segments]
    font=ImageFont.truetype(str(font_path),font_size);metric=font_size/sum(font.getmetrics())
    records=[];pending={}
    for row in segments:
        words=[w['word'] for w in row.get('words') or [{'word':row['text']}]]
        identity=json.dumps(['libass-tv-rgb-v3',words,width,height,baseline,font_size,font_path.stat().st_mtime_ns],ensure_ascii=False)
        key=hashlib.sha256(identity.encode('utf-8')).hexdigest();path=cache/(key+'.json')
        if path.is_file():records.append(json.loads(path.read_text(encoding='utf-8')));continue
        records.append(key);pending[key]=words
    if pending:
        executable=root/'tools/setup-runtime/ffmpeg/bin/ffmpeg.exe'
        ffmpeg=str(executable) if executable.is_file() else shutil.which('ffmpeg')
        if not ffmpeg:raise ValueError('Yazı konumunu ölçmek için FFmpeg bulunamadı.')
        with tempfile.TemporaryDirectory(dir=cache) as temporary:
            folder=Path(temporary)
            header=['[Script Info]','ScriptType: v4.00+',f'PlayResX: {width}',f'PlayResY: {height}','[V4+ Styles]',
                    'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
                    f'Style: Active,Segoe UI,{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,1,0,2,120,120,0,1',
                    '[Events]','Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
            colors=[]
            for i,(key,words) in enumerate(pending.items()):
                if len(words)>2197:raise ValueError('Bir söz satırı çok uzun; daha kısa satırlara bölün.')
                scale=min(1,(width-120)/max(1,font.getlength(' '.join(words))*metric))
                palette=[(64+j%13*14,65+j//13%13*14,66+j//169*14) for j in range(len(words))]
                label=' '.join(f'{{\\1c&H{b:02X}{g:02X}{r:02X}&}}{escape_ass(word)}' for word,(r,g,b) in zip(words,palette))
                header.append(f'Dialogue: 0,{ass_time(i)},{ass_time(i+1)},Active,,0,0,0,,{{\\an2\\pos({width/2:.3f},{baseline})\\fscx{scale*100:.4f}\\q2\\bord1\\shad0}}{label}')
                colors.append((key,palette,scale))
            (folder/'layout.ass').write_text('\n'.join(header),encoding='utf-8')
            subprocess.run([ffmpeg,'-y','-v','error','-f','lavfi','-i',f'color=black:s={width}x{height}:r=1:d={len(colors)}',
                            '-vf','format=rgb24,subtitles=layout.ass','-frames:v',str(len(colors)),'-threads','1','glyph-%03d.png'],cwd=folder,check=True,capture_output=True)
            for i,(key,palette,scale) in enumerate(colors):
                origin_y=max(0,baseline-font_size*2)
                pixels=np.asarray(Image.open(folder/f'glyph-{i+1:03d}.png').convert('RGB').crop((0,origin_y,width,min(height,baseline+font_size*2)))).astype('int16')
                bounds=[];top=height;bottom=0
                for color in palette:
                    reference=np.rint(16+np.array(color)*219/255).astype('int16')
                    mask=np.all(np.abs(pixels-reference)<=1,axis=2);yy,xx=np.where(mask)
                    if not len(xx):raise ValueError('Bir kelimenin video yazı konumu ölçülemedi; satırı kısaltın.')
                    bounds.append([int(xx.min()),int(xx.max())]);top=min(top,int(yy.min())+origin_y);bottom=max(bottom,int(yy.max())+origin_y)
                boxes=[[max(0,a-2,math.ceil((bounds[j-1][1]+a)/2) if j else 0),
                        min(width,b+3,math.floor((b+bounds[j+1][0])/2) if j+1<len(bounds) else width)] for j,(a,b) in enumerate(bounds)]
                value={'boxes':boxes,'ink_top':top-2,'ink_bottom':bottom+3,'scale':scale}
                pending[key]=value
                target=cache/(key+'.json');temp=target.with_name(target.stem+uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(value),encoding='utf-8');os.replace(temp,target)
    return [pending[item] if isinstance(item,str) else item for item in records]


def row_gradient_layers(events, baseline, font_size, width, height, motion, theme, geometry=None):
    """Intersect the timed horizontal sweep with a gradient owned by ONE row.

    Screen-space clips follow the same translation/scale as their glyphs.
    Separate row layers prevent a transitioning neighbour sharing its gradient.
    """
    palettes={'gold':((201,119,0),(255,246,163)), 'neon':((0,141,185),(183,251,255)),
              'cyberpunk':((147,26,152),(255,193,242)), 'emerald':((0,128,75),(180,255,211))}
    def seconds(value):
        h,m,s=value.split(':');return int(h)*3600+int(m)*60+float(s)
    result=[]
    for event in events:
        fields=event.split(',',9)
        if fields[0]!='Dialogue: 2':result.append(event);continue
        at,until=seconds(fields[1]),seconds(fields[2]);body=fields[9]
        rectangles=re.findall(r'\\clip\(([^)]+)\)',body)
        if not rectangles:result.append(event);continue
        initial=tuple(map(float,rectangles[0].split(',')))
        targets=[(int(b),tuple(map(float,rect.split(',')))) for a,b,rect in
                 re.findall(r'\\t\((\d+),(\d+),\\clip\(([^)]+)\)\)',body)]
        curve=[(0,initial)]+targets
        def rect_at(delta):
            for (a,first),(b,last) in zip(curve,curve[1:]):
                if delta<=b:
                    p=max(0,min(1,(delta-a)/max(1,b-a)))
                    return tuple(x+(y-x)*p for x,y in zip(first,last))
            return curve[-1][1]
        body=re.sub(r'\\t\(\d+,\d+,\\clip\([^)]+\)\)','',body)
        body=re.sub(r'\\clip\([^)]+\)','',body)
        body=re.sub(r'\\t\(\d+,\d+,\\1c&H[0-9A-F]+&\)','',body)
        body=re.sub(r'\\1c&H[0-9A-F]+&','',body)
        duration=max(1,round((until-at)*1000))
        keys={0,duration,*[t for t,_ in curve if 0<t<duration]}
        if motion:
            for absolute in (motion['leave'],motion['leave']+.48,motion['shrink'],motion['shrink']+.48):
                offset=round((absolute-at)*1000)
                if 0<offset<duration:keys.add(offset)
            for absolute in [motion['leave']+j*.04 for j in range(25)]:
                offset=round((absolute-at)*1000)
                if 0<offset<duration:keys.add(offset)
        keys=sorted(keys);dark,light=palettes.get(theme,palettes['gold'])
        for band in range(16):
            y0=geometry['ink_top'] if geometry else baseline-font_size
            y1=geometry['ink_bottom'] if geometry else baseline
            top=y0+band*(y1-y0)/16;bottom=y0+(band+1)*(y1-y0)/16
            amount=1-(band+.5)/16;r,g,b=[round(a+(z-a)*amount) for a,z in zip(dark,light)]
            def clip(delta):
                left,_,right,_=rect_at(delta);t=at+delta/1000
                offset=0;scale=1
                if motion:
                    offset=(180 if height>width else 160)*max(0,min(1,(t-motion['leave'])/.48))
                    scale=1-.35*max(0,min(1,(t-motion['shrink'])/.48))
                left=width/2+(left-width/2)*scale;right=width/2+(right-width/2)*scale
                return f'\\clip({left:.2f},{baseline+(top-baseline)*scale+offset:.2f},{right:.2f},{baseline+(bottom-baseline)*scale+offset:.2f})'
            tags=f'\\1c&H{b:02X}{g:02X}{r:02X}&'+clip(0)
            tags+=''.join(f'\\t({a},{b},{clip(b)})' for a,b in zip(keys,keys[1:]))
            result.append(','.join(fields[:9])+','+body.replace('}',tags+'}',1))
    return result


def progress_events(duration, width, theme='gold'):
    """Continuous media-time fill; countdown uses the same full audio duration."""
    from karaoke_timing import ass_time
    if not math.isfinite(duration) or duration <= 0:
        return []
    color={'gold':'5BBBF3','neon':'EAD05B','cyberpunk':'F169DC','emerald':'ACDA57'}.get(theme,'5BBBF3')
    left,right,y=110,width-390,205
    end=ass_time(duration)
    drawing=f'm {left} {y-3} l {right} {y-3} {right} {y+3} {left} {y+3}'
    events=[f'Dialogue: 2,0:00:00.00,{end},Active,,0,0,0,,{{\\an7\\pos(0,0)\\bord0\\shad0\\1c&H{color}&\\clip({left},0,{left},220)\\t(0,{round(duration*1000)},\\clip({left},0,{right},220))\\p1}}{drawing}']
    for remaining in range(math.ceil(duration),0,-1):
        second=max(0,duration-remaining)
        label=f'{remaining//60:02d}:{remaining%60:02d} KALDI'
        events.append(f'Dialogue: 2,{ass_time(second)},{ass_time(duration-remaining+1)},Active,,0,0,0,,{{\\an4\\pos({right+24},{y})\\fnSegoe UI\\fs20\\b0\\bord0\\shad0\\1c&HCDC8C4&}}{label}')
    return events


def row_motion(segment, last=False, next_start=float('inf')):
    from karaoke_timing import is_music_label
    start,end=segment['start'],segment['end']
    leave=max(start,min(end+(0 if is_music_label(segment['text']) else 2 if last else .35),next_start)-.48)
    fade=max(end,leave+.48)
    return dict(enter=max(0,start-.48),leave=leave,shrink=max(end,leave),fade=fade,end=fade+.36)


def lead_cue_events(show_start, spoken_start, width, baseline, theme):
    """A visible three-second preparation clock, independent of lyric fill."""
    from karaoke_timing import ass_time
    start=max(show_start,spoken_start-3);end=spoken_start-.48
    if end<=start:return []
    color={'gold':'00C8FF','neon':'FFE606','cyberpunk':'E040FF','emerald':'70EA20'}.get(theme,'00C8FF')
    left,right,y=width/2-70,width/2+70,baseline+62
    fraction=max(0,min(1,(start-spoken_start+3)/3));initial=left+(right-left)*fraction
    final=left+(right-left)*(1-.48/3)
    drawing=f'm {left} {y} l {right} {y} {right} {y+3} {left} {y+3}'
    events=[f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Active,,0,0,0,,{{\\an7\\pos(0,0)\\bord0\\shad0\\1c&H{color}&\\fad(120,150)\\clip({left},0,{initial},{y+4})\\t(0,{round((end-start)*1000)},\\clip({left},0,{final},{y+4}))\\p1}}{drawing}']
    for remaining in (3,2,1):
        a=max(start,spoken_start-remaining);b=min(end,spoken_start-remaining+1)
        if b>a:events.append(f'Dialogue: 0,{ass_time(a)},{ass_time(b)},Active,,0,0,0,,{{\\an2\\pos({width/2},{baseline+48})\\fs18\\b0\\bord0\\shad0\\1c&HC6B9B4&}}{remaining} sn · HAZIRLAN')
    return events


def soft_word_events(segment, display_end, width, height, baseline, font_size, theme, motion=None, geometry=None):
    """Horizontal feathered sweep on measured media times, with a white base."""
    from PIL import ImageFont
    from karaoke_timing import ass_time,escape_ass
    font_path=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/segoeuib.ttf'
    if not font_path.is_file():return None
    font=ImageFont.truetype(str(font_path),font_size)
    words=segment.get('words') or [{'word':segment['text'],'start':segment['start'],'end':segment['end'],'timing_source':'estimated'}]
    pieces=[w['word']+(' ' if i<len(words)-1 else '') for i,w in enumerate(words)]
    # libass normalizes font size to ascent + descent, whereas Pillow uses em.
    metric_scale=font_size/sum(font.getmetrics())
    lengths=[font.getlength(p)*metric_scale for p in pieces];total=sum(lengths)
    scale=geometry['scale'] if geometry else min(1,(width-120)/max(total,1));x=(width-total*scale)/2
    color={'gold':'00C8FF','neon':'FFE606','cyberpunk':'E040FF','emerald':'70EA20'}.get(theme,'00C8FF')
    settled={'gold':'0098FF','neon':'E6B800','cyberpunk':'BD00D8','emerald':'50BB00'}.get(theme,'0098FF')
    if motion:display_end=motion['end']
    events=[];row_start=ass_time(segment['start']);row_end=ass_time(display_end)
    pos=f'\\an2\\pos({width/2:.3f},{baseline})\\fscx{scale*100:.4f}\\q2\\bord1\\shad0'
    label=escape_ass(''.join(pieces))
    # All layers draw ONE centered line. Glyph spacing is owned by libass,
    # never by a separately positioned dialogue for each individual word.
    events.append(f'Dialogue: 1,{row_start},{row_end},Active,,0,0,0,,{{{pos}\\1c&HC6B9B4&}}{label}')
    for index,(word,piece,length) in enumerate(zip(words,pieces,lengths)):
        if geometry:x=geometry['boxes'][index][0]
        right=x+font.getlength(word['word'])*metric_scale*scale
        if geometry:right=geometry['boxes'][index][1]
        start,end=word['start'],word['end']
        if end>start and word.get('timing_source')!='estimated':
            duration=max(1,round((end-start)*1000));half=max(1,round(duration/2))
            feather=min(48,(right-x)*.35);middle=(x+right)/2
            intervals=[(x,middle-feather/2,0)]
            # The feather expands through the word and contracts to zero at
            # completion, so the last letters never jump to a solid color.
            for band in range(16):
                alpha=(band+.5)/16
                alpha=alpha*alpha*(3-2*alpha)
                intervals.append((middle-feather/2+band*feather/16,middle-feather/2+(band+1)*feather/16,round(255*alpha)))
            for band,(left_mid,right_mid,alpha) in enumerate(intervals):
                left_end=x if band==0 else right
                initial=f'\\clip({round(x)},0,{round(x)},{height})'
                midway=f'\\clip({round(left_mid)},0,{round(right_mid)},{height})'
                final=f'\\clip({round(left_end)},0,{round(right)},{height})'
                events.append(f'Dialogue: 2,{ass_time(start)},{ass_time(min(end,display_end))},Active,,0,0,0,,{{{pos}\\1c&H{color}&\\t(0,{duration},\\1c&H{settled}&)\\alpha&H{alpha:02X}&{initial}\\t(0,{half},{midway})\\t({half},{duration},{final})}}{label}')
            if display_end>end:
                events.append(f'Dialogue: 2,{ass_time(end)},{row_end},Active,,0,0,0,,{{{pos}\\1c&H{settled}&\\clip({round(x)},0,{round(right)},{height})}}{label}')
        x+=length*scale
    events=row_gradient_layers(events,baseline,font_size,width,height,motion,theme,geometry)
    if motion:
        # Every overlay uses offsets from its own event start to the SAME
        # media-time handoff, including a syllable still filling during exit.
        distance=180 if height>width else 160
        animated=[]
        for event in events:
            fields=event.split(',',9)
            h,m,s=fields[1].split(':');at=int(h)*3600+int(m)*60+float(s)
            move_start=max(0,round((motion['leave']-at)*1000))
            move_end=max(0,round((motion['leave']+.48-at)*1000))
            fraction=max(0,min(1,(at-motion['leave'])/.48))
            position=(f'\\move({width/2:.3f},{baseline+distance*fraction:.3f},{width/2:.3f},{baseline+distance},{move_start},{move_end})'
                      if move_end else f'\\pos({width/2:.3f},{baseline+distance})')
            event=event.replace(f'\\pos({width/2:.3f},{baseline})',position)
            shrink_fraction=max(0,min(1,(at-motion['shrink'])/.48))
            event=event.replace(f'\\fscx{scale*100:.4f}',f'\\fscx{scale*(1-.35*shrink_fraction)*100:.4f}\\fscy{(1-.35*shrink_fraction)*100:.4f}')
            shrink_start=max(0,round((motion['shrink']-at)*1000));shrink_end=max(1,round((motion['shrink']+.48-at)*1000))
            event=event.replace('}',f'\\t({shrink_start},{shrink_end},\\fscx{scale*65:.4f}\\fscy65)'+'}',1)
            fade_start=max(0,round((motion['fade']-at)*1000));fade_end=max(1,round((motion['end']-at)*1000))
            event=event.replace('}',f'\\t({fade_start},{fade_end},\\alpha&HFF&)'+ '}',1)
            animated.append(event)
        if segment['start']>motion['enter']:
            milliseconds=round((segment['start']-motion['enter'])*1000)
            animated.insert(0,f'Dialogue: 1,{ass_time(motion["enter"])},{row_start},Active,,0,0,0,,{{\\an2\\move({width/2},{baseline-distance},{width/2},{baseline},0,{milliseconds})\\fs{font_size*.4:.3f}\\fscx{scale*100:.4f}\\t(0,{milliseconds},\\fs{font_size})\\fad(240,0)\\q2\\bord1\\shad0\\1c&HC6B9B4&}}{label}')
            from karaoke_timing import is_music_label
            if not is_music_label(segment['text']):
                ghost_end=min(segment['start'],motion['enter']+.24)
                animated.append(f'Dialogue: 0,{ass_time(motion["enter"])},{ass_time(ghost_end)},Upcoming,,0,0,0,,{{\\an2\\pos({width/2},{baseline-distance})\\fs{font_size*.4:.3f}\\b0\\q2\\bord0\\shad0\\1c&H9C9595&\\fad(0,{round((ghost_end-motion["enter"])*1000)})}}{label}')
        return animated
    return events


def gradient_masks(theme, width, height, baseline, font_size):
    """Disjoint ASS clips apply a vertical gradient to the timed primary fill."""
    colors={'gold':((255,241,172),(244,154,85)), 'neon':((176,255,241),(102,153,255)),
            'cyberpunk':((255,178,237),(170,121,255)), 'emerald':((196,255,226),(63,188,169))}
    light,dark=colors.get(theme,colors['gold'])
    cuts=[0]+[round(baseline-font_size+i*font_size/12) for i in range(13)]+[height]
    result=[]
    for top,bottom in zip(cuts,cuts[1:]):
        amount=max(0,min(1,((top+bottom)/2-(baseline-font_size))/font_size))
        r,g,b=[round(a+(z-a)*amount) for a,z in zip(light,dark)]
        result.append(f'{{\\clip(0,{top},{width},{bottom})\\1c&H{b:02X}{g:02X}{r:02X}&}}')
    return result


def ambient_events(duration, width, height):
    from karaoke_timing import ass_time
    events=[]
    for index in range(14):
        x=24+(index*13)%32 if index%2==0 else width-24-(index*13)%32
        start=index*.65
        while start<duration:
            events.append(f'Dialogue: -1,{ass_time(start)},{ass_time(start+12)},Active,,0,0,0,,{{\\an7\\move({x},{height-70},{x+12},170)\\fad(1800,1800)\\1c&HDDCCBB&\\alpha&H90&\\bord0\\shad0\\p1}}m 0 0 l 3 0 3 3 0 3')
            start+=12
    return events


def studio_background(directory, theme='gold', vertical=False):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import numpy as np
    palette = {'gold': (243, 187, 91), 'neon': (91, 208, 234),
               'cyberpunk': (220, 105, 241), 'emerald': (87, 218, 172)}
    accent = palette.get(theme, palette['gold'])
    path = Path(directory) / f'studio_editorial_v4_{theme if theme in palette else "gold"}_{"portrait" if vertical else "landscape"}.png'
    if path.exists():
        return path
    width, height = (1080, 1920) if vertical else (1920, 1080)
    y, x = np.mgrid[0:height:4, 0:width:4].astype(float)
    x /= width; y /= height
    warm = np.exp(-(((x-.06)/.42)**2 + ((y-.13)/.38)**2)*2)
    cool = np.exp(-(((x-.94)/.4)**2 + ((y-.85)/.45)**2)*2)
    base = np.zeros((*x.shape, 3)) + [8, 10, 19]
    base += warm[...,None] * np.array(accent)[None,None,:] * .17
    base += cool[...,None] * np.array([92, 82, 187])[None,None,:] * .27
    image = Image.fromarray(base.clip(0,255).astype('uint8')).resize((width,height),Image.Resampling.BICUBIC).convert('RGBA')
    ornaments = Image.new('RGBA', image.size); draw = ImageDraw.Draw(ornaments)
    # Open typography stage, with a sculptural halo rather than a giant UI card.
    cx,cy=width-160,190
    for radius in (82,98,118,146,180,222):
        draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),outline=(*accent,40 if radius<150 else 18),width=1)
    draw.arc((cx-119,cy-119,cx+119,cy+119),205,310,fill=(*accent,180),width=3)
    for i in range(7):
        bar=14+((i*19)%41)
        draw.rounded_rectangle((cx-38+i*12,cy-bar/2,cx-33+i*12,cy+bar/2),radius=2,fill=(*accent,150))
    for i in range(18):
        draw.line((80+i*18,height-470,80+i*18,height-340+(i%3)*8),fill=(156,144,210,12),width=1)
    draw.rounded_rectangle((110,202,width-390,208),radius=3,fill=(215,211,234,28))
    label_y=745 if vertical else 300
    draw.rounded_rectangle((width/2-82,label_y,width/2+82,label_y+38),radius=19,fill=(*accent,14),outline=(*accent,40),width=1)
    try:
        font=ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf',16)
        small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
        draw.text((width/2,label_y+18),'S I R A D A K İ',font=font,anchor='mm',fill=(*accent,190))
        draw.text((110,158),'K A R A O K E   /   S T Ü D Y O',font=small,fill=(204,201,220,160))
    except OSError:
        pass
    draw.line((width/2-30,label_y-48,width/2+30,label_y-48),fill=(*accent,160),width=2)
    bottom=height-110
    draw.rounded_rectangle((90,height-200,width-90,bottom+25),radius=28,fill=(17,21,35,170),outline=(185,187,220,30),width=1)
    image = Image.alpha_composite(image,ornaments)
    glow=Image.new('RGBA',image.size);gd=ImageDraw.Draw(glow)
    gd.line((width*.35,height-205,width*.65,height-205),fill=(*accent,80),width=6)
    image=Image.alpha_composite(image,glow.filter(ImageFilter.GaussianBlur(24)))
    temporary=path.with_name(path.stem+uuid.uuid4().hex+'.png')
    image.convert('RGB').save(temporary);os.replace(temporary,path)
    return path
