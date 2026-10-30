"""Validate stored syllable intervals before playback; stale metadata is ignored."""
import math
import unicodedata


def text_key(text):
    text=unicodedata.normalize('NFC',text).replace('İ','i').replace('I','ı').casefold()
    return ''.join(c for c in text if unicodedata.category(c)[0] in 'LMN')


def syllable_pieces(word):
    punctuation_parts=bool(word.get('timing_parts'))
    parts=word.get('timing_parts') if punctuation_parts else word.get('syllables') or []
    if not isinstance(parts,list) or not parts or word.get('needs_review') or word.get('timing_source') in ('estimated','repeat_inferred'):return []
    if any(not isinstance(p,dict) or not isinstance(p.get('text'),str) for p in parts):return []
    raw=unicodedata.normalize('NFC',word['word'])
    if text_key(''.join(p['text'] for p in parts))!=text_key(raw):return []
    reference=word.get('timing_parts_reference') if punctuation_parts else word.get('syllable_reference')
    if punctuation_parts and reference is None:return []
    if reference is not None:
        if not isinstance(reference,dict) or not isinstance(reference.get('word_text'),str) or reference.get('word_start')!=word['start'] or reference.get('word_end')!=word['end'] or text_key(reference['word_text'])!=text_key(raw):return []
    else:
        edges=[parts[0].get('start'),parts[-1].get('end')]
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in edges):return []
        if abs(edges[0]-word['start'])>.02 or abs(edges[1]-word['end'])>.02:return []
    result=[];cursor=0;previous=word['start']
    for index,part in enumerate(parts):
        values=[part.get(k) for k in ('start','end','score')]
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):return []
        start,end,score=values
        if part.get('needs_review') or score<(.5 if punctuation_parts else .55) or not word['start']<=previous<=start<end<=word['end']:return []
        count=len(text_key(part['text']));first=cursor
        while cursor<len(raw) and count:
            if unicodedata.category(raw[cursor])[0] in 'LMN':count-=1
            cursor+=1
        if count:return []
        if index==len(parts)-1:cursor=len(raw)
        result.append({'text':raw[first:cursor],'start':start,'end':end,'score':score})
        previous=end
    return result


def syllable_fill(word,time):
    parts=syllable_pieces(word)
    if not parts:return None
    weights=[len(p['text']) for p in parts];total=sum(weights)
    return sum(weight*max(0,min(1,(time-part['start'])/(part['end']-part['start']))) for part,weight in zip(parts,weights))/total
