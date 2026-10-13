import copy
import unittest
import numpy as np
from karaoke_repeat_spotting import expand_supplied_rows,select_occurrences,bound_terminal_phrase

VOCAB={c:i+1 for i,c in enumerate('|abcdefghijklmnopqrstuvwxyzıüşöçğ')};VOCAB['[PAD]']=0

def evidence(texts):
    frames=[]
    def frame(index):
        x=np.full(len(VOCAB),1e-6,dtype='float32');x[index]=.999;return np.log(x/x.sum())
    frames.extend([frame(0)]*50)
    for text in texts:
        for char in text.lower().replace(' ','|'):
            frames.extend([frame(VOCAB[char])]*4);frames.extend([frame(0)]*2)
        frames.extend([frame(0)]*70)
    return np.asarray(frames)


def hit(text,start,end,quality=.9,path=-.2,similarity=.95):
    tokens=text.split();step=(end-start)/len(tokens)
    return {'text':text,'start':start,'end':end,'path_score':path,'text_similarity':similarity,
        'confidence':quality,'words':[{'word':t,'start':start+i*step,'end':start+(i+1)*step,'probability':quality} for i,t in enumerate(tokens)]}

class RepeatSpottingTests(unittest.TestCase):
    def test_terminal_context_bounds_prefix_without_copying_unheard_suffix(self):
        audio=evidence(['gel bana don'])
        rows=[{'id':'a','text':'GEL BANA'},{'id':'b','text':'GEL BANA DON ARTIK'}]
        bounded=bound_terminal_phrase(hit('GEL BANA',1,len(audio)*.02-1.4),rows,[audio,audio.copy()],VOCAB)
        self.assertIsNotNone(bounded)
        self.assertEqual([w['word'] for w in bounded['words']],['GEL','BANA'])
        self.assertLess(bounded['end'],len(audio)*.02-1.4)
        self.assertTrue(bounded['terminal_bounded'])
    def test_terminal_silence_and_single_channel_are_not_corroboration(self):
        audio=evidence(['gel bana don']);silence=np.full_like(audio,-20);silence[:,0]=0
        rows=[{'id':'a','text':'GEL BANA DON ARTIK'}]
        candidate=hit('GEL BANA',1,3)
        self.assertIsNone(bound_terminal_phrase(candidate,rows,[audio],VOCAB))
        self.assertIsNone(bound_terminal_phrase(candidate,rows,[audio,silence],VOCAB))
    def test_detects_repeated_supplied_text_and_second_click_is_idempotent(self):
        rows=[{'id':'a','text':'GEL BANA','start':0,'end':0,'words':[]}]
        audio=evidence(['gel bana','gel bana'])
        result,report,_=expand_supplied_rows(rows,audio,VOCAB)
        self.assertEqual(report['repeated_rows_added'],1)
        self.assertEqual([r['text'] for r in result],['GEL BANA','GEL BANA'])
        self.assertEqual(result[1]['repeat_source_id'],'a')
        again,report,_=expand_supplied_rows(result,audio,VOCAB)
        self.assertEqual(report['repeated_rows_added'],0)
        self.assertEqual([r['id'] for r in again],[r['id'] for r in result])
    def test_silence_does_not_create_repeat(self):
        frames=np.full((1000,len(VOCAB)),1e-8,dtype='float32');frames[:,0]=.999
        result,report,_=expand_supplied_rows([{'id':'a','text':'GEL BANA'}],np.log(frames),VOCAB)
        self.assertEqual(report['repeated_rows_added'],0)
        self.assertEqual(len(result),1)
    def test_competing_lyric_variant_uses_stronger_evidence(self):
        rows=[{'id':'a','text':'NASIL TUTTUN ELLERIMI'},{'id':'b','text':'NASIL DOLDURDUN YERIMI'}]
        candidates=[hit(rows[0]['text'],1,2),hit(rows[1]['text'],3,4),
            hit(rows[0]['text'],5,6,path=-.9,similarity=.71),
            hit(rows[1]['text'],5,6,path=-2.05,similarity=.56)]
        chosen=select_occurrences(rows,candidates,VOCAB)
        copies=[h for h in chosen if h['kind']=='repeat']
        self.assertEqual([h['text'] for h in copies],[rows[0]['text']])
    def test_weak_seventy_millisecond_interjection_is_rejected(self):
        rows=[{'id':'a','text':'AH BU GONUL'},{'id':'b','text':'BU GONUL'}]
        wrong=hit(rows[0]['text'],5,6)
        wrong['words'][0].update(end=5.07,probability=.21)
        chosen=select_occurrences(rows,[hit(rows[0]['text'],1,2),hit(rows[1]['text'],3,4),wrong,hit(rows[1]['text'],5.07,6)],VOCAB)
        self.assertEqual([h['text'] for h in chosen if h['kind']=='repeat'],[rows[1]['text']])
    def test_supplied_row_order_is_not_changed_by_detected_early_phrase(self):
        rows=[{'id':'a','text':'GEL BANA'},{'id':'b','text':'DON GEL'}]
        candidates=[hit('DON GEL',1,2),hit('GEL BANA',3,4),hit('DON GEL',5,6)]
        selected=select_occurrences(rows,candidates,VOCAB)
        self.assertEqual([h['text'] for h in selected if h['kind']=='original'],['GEL BANA','DON GEL'])
        self.assertEqual([h for h in selected if h['kind']=='repeat'],[])
    def test_locked_row_never_produces_automatic_copy(self):
        rows=[{'id':'a','text':'GEL BANA','locked':True}]
        selected=select_occurrences(rows,[hit('GEL BANA',1,2),hit('GEL BANA',3,4)],VOCAB)
        self.assertEqual([h for h in selected if h['kind']=='repeat'],[])
