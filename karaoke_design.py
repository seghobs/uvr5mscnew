"""Shared artwork for preview and final karaoke composition."""
from pathlib import Path
import os
import uuid
import math


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


def soft_word_events(segment, display_end, width, height, baseline, font_size, theme):
    """Horizontal feathered sweep on measured media times, with a white base."""
    from PIL import ImageFont
    from karaoke_timing import ass_time,escape_ass
    font_path=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/segoeuib.ttf'
    if not font_path.is_file():return None
    font=ImageFont.truetype(str(font_path),font_size)
    words=segment.get('words') or []
    if not words:return None
    pieces=[w['word']+(' ' if i<len(words)-1 else '') for i,w in enumerate(words)]
    lengths=[font.getlength(p) for p in pieces];total=sum(lengths)
    scale=min(1,(width-120)/max(total,1));x=(width-total*scale)/2
    color={'gold':'ACF1FF','neon':'F1FFB0','cyberpunk':'EDB2FF','emerald':'E2FFC4'}.get(theme,'ACF1FF')
    events=[];row_start=ass_time(segment['start']);row_end=ass_time(display_end)
    for word,piece,length in zip(words,pieces,lengths):
        right=x+font.getlength(word['word'])*scale
        pos=f'\\an1\\pos({x:.3f},{baseline})\\fscx{scale*100:.4f}\\q2\\bord0\\shad0'
        label=escape_ass(piece)
        events.append(f'Dialogue: 1,{row_start},{row_end},Active,,0,0,0,,{{{pos}\\1c&HFFFFFF&}}{label}')
        start,end=word['start'],word['end']
        if end>start and word.get('timing_source')!='estimated':
            duration=max(1,round((end-start)*1000));feather=min(12,(right-x)*.15)
            intervals=[(x-feather,x-feather, x,right-feather,0)]
            # Each translucent band follows the same acoustic sweep front.
            for band in range(6):
                a=-feather+band*feather/6;b=a+feather/6
                intervals.append((x+a,x+b,right+a,right+b,round(255*(band+.5)/6)))
            for left0,right0,left1,right1,alpha in intervals:
                if alpha==0:left0=x;right0=x-feather;left1=x
                initial=f'\\clip({round(left0)},0,{round(max(left0,right0))},{height})'
                final=f'\\clip({round(left1)},0,{round(max(left1,right1))},{height})'
                events.append(f'Dialogue: 2,{ass_time(start)},{ass_time(min(end,display_end))},Active,,0,0,0,,{{{pos}\\1c&H{color}&\\alpha&H{alpha:02X}&{initial}\\t(0,{duration},{final})}}{label}')
            if display_end>end:
                events.append(f'Dialogue: 2,{ass_time(end)},{row_end},Active,,0,0,0,,{{{pos}\\1c&H{color}&}}{label}')
        x+=length*scale
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
    path = Path(directory) / f'studio_editorial_v3_{theme if theme in palette else "gold"}_{"portrait" if vertical else "landscape"}.png'
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
    label_y=1120 if vertical else 645
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
