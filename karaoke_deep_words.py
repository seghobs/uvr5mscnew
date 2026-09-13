"""Multi-pass local recognition. Returns alternatives, never writes project lyrics."""
import math
import re
from difflib import SequenceMatcher


def filter_english_adlibs(words):
    """Drop common English backing phrases without moving Turkish word times.

    Match whole tokens/phrases; Turkish words such as 'hey', 'of', 'can' and
    'on' must not be removed just because they also occur in English.
    """
    phrases = [
        ('i', 'love', 'you'), ('thank', 'you'), ('thanks',),
        ('lets', 'go'), ('let', 'us', 'go'), ('come', 'on'),
        ('you', 'know'), ('are', 'you', 'ready'), ('oh', 'my', 'god'),
        ('yes',), ('yeah',), ('yep',), ('yup',), ('okay',), ('okey',),
        ('ok',), ('hello',), ('baby',), ('alright',),
    ]
    # Recognition is uppercased with Turkish casing; undo it for English tokens.
    def token(text):
        return re.sub(r'[^a-zçğıöşü0-9]', '', text.replace('İ', 'i').replace('I', 'i').lower())
    labels = [token(w['word']) for w in words]
    kept, rejected = [], []
    index = 0
    while index < len(words):
        match = next((phrase for phrase in phrases
                      if labels[index:index+len(phrase)] == list(phrase)
                      and all(words[j]['start']-words[j-1]['end'] < 1
                              for j in range(index+1,index+len(phrase)))), None)
        if match:
            rejected.extend(w['word'] for w in words[index:index+len(match)])
            index += len(match)
        else:
            kept.append(words[index])
            index += 1
    return kept, rejected


def normalized(text):
    return re.sub(r'[^a-zçğıöşü0-9 ]', '', text.replace('I','ı').replace('İ','i').lower()).strip()


def rank_candidates(candidates):
    for candidate in candidates:
        text=normalized(candidate['text'])
        peers=[c for c in candidates if c is not candidate]
        agreement=sum(SequenceMatcher(None,text,normalized(c['text'])).ratio() for c in peers)/max(1,len(peers))
        candidate['agreement']=round(agreement,3)
        candidate['needs_review']=True
    return sorted(candidates,key=lambda c:(c['agreement'],c['probability']),reverse=True)


def deep_words(path,start,end,get_model,progress=lambda *args:None):
    import numpy as np
    import soundfile as sf
    import torch
    import torchaudio.functional as AF
    info=sf.info(path)
    if not all(math.isfinite(x) for x in (start,end)) or start<0 or end<=start or end>info.duration or end-start>60:
        raise ValueError('Ses içinde en fazla 60 saniyelik bir aralık seçin.')
    samples,rate=sf.read(path,start=int(start*info.samplerate),stop=int(min(info.duration,end+14)*info.samplerate),dtype='float32')
    if samples.ndim==2:samples=samples.mean(axis=1)
    if not samples.size or not np.isfinite(samples).all():raise ValueError('Ses bölümü okunamadı.')
    if np.max(np.abs(samples))<1e-5:return {'candidates':[],'message':'Bu aralıkta duyulabilir ses yok.'}
    wave=AF.resample(torch.from_numpy(samples),rate,16000).numpy()
    peak_rms=max(float(np.sqrt(np.mean(wave[i:i+1600]**2))) for i in range(0,len(wave),1600))
    candidates=[]
    for run,(key,chunked) in enumerate([('large-v3',False),('large-v3-turbo',False),('large-v3',True),('large-v3-turbo','onset')]):
        progress(.05+run*.23,f'Ses yeniden çözümleniyor: {run+1}/4')
        model=get_model(key)
        length=len(wave)/16000
        requested=end-start
        chunks=[(0,length,0,requested)] if not chunked else [(max(0,t-2),min(length,t+24),t,min(requested,t+12)) for t in range(0,math.ceil(requested),12)]
        if chunked=='onset':
            energy=np.array([np.sqrt(np.mean(wave[i:i+1600]**2)) for i in range(0,int(requested*16000),1600)])
            active=np.flatnonzero(energy>max(1e-5,float(energy.max())*.12))
            focus=max(0,float(active[0])*.1-2) if len(active) else 0
            chunks=[(focus,min(length,focus+28),0,requested)]
        words=[]; rejected=[]
        for a,b,owner_a,owner_b in chunks:
            decoded,_=model.transcribe(wave[int(a*16000):int(b*16000)],language='tr',beam_size=10,
                temperature=0.,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
            for segment in decoded:
                # A subtitle-credit hallucination is retained as a rejected diagnostic.
                if re.fullmatch(r'\s*(altyaz[ıi]\s*)?m\s*[.]?\s*k\s*[.]?\s*',segment.text,re.IGNORECASE):
                    rejected.append(segment.text.strip());continue
                for w in segment.words or []:
                    s,e=a+w.start,a+w.end
                    if not owner_a<=(s+e)/2<owner_b or not 0<=s<e<=requested:continue
                    evidence=wave[int(s*16000):int(e*16000)]
                    if not evidence.size or float(np.sqrt(np.mean(evidence**2)))<max(1e-6,peak_rms*.01):
                        rejected.append(w.word.strip());continue
                    words.append({'word':w.word.strip().replace('i','İ').replace('ı','I').upper(),
                        'start':start+s,'end':start+e,'probability':float(w.probability),
                        'timing_source':'whisper','needs_review':True})
        words.sort(key=lambda w:w['start'])
        words, english_rejected = filter_english_adlibs(words)
        rejected.extend(english_rejected)
        if words:
            candidates.append({'label':['Geniş bağlam','İkinci model','Kısa bölümler','Vokal girişine odaklanma'][run],
                'text':' '.join(w['word'] for w in words),'words':words,'rejected':rejected,
                'probability':sum(w['probability'] for w in words)/len(words)})
        model=None
    message = ('4 deneme tamamlandı. Yaygın İngilizce ünlem ve kalıplar süzüldü. Alternatifleri dinleyerek karşılaştırın.'
               if candidates else 'Türkçe söz adayı bulunamadı. Yazdığın sözleri sesle hizalamayı deneyin; mevcut sözler korundu.')
    return {'candidates':rank_candidates(candidates),'message':message}
