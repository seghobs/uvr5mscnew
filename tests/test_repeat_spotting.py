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
    def test_waveform_search_uses_verified_prefix_inside_longer_refrain(self):
        from unittest.mock import patch
        from karaoke_repeat_spotting import waveform_repeat_hits
        rows=[{'id':'short','text':'GEL BANA'},{'id':'full','text':'GEL BANA DON BURAYA'}]
        selected=[hit('GEL BANA',1,3),hit('GEL BANA DON BURAYA',10,15)]
        def recover(references,_path,**_kwargs):
            prefix=next(r for r in references if r['text']=='GEL BANA' and r['start']==10)
            self.assertEqual(prefix['end'],12.5)
            copy_row=copy.deepcopy(prefix);copy_row['repeat_source_id']=prefix['id']
            for w in copy_row['words']:w['start']+=20;w['end']+=20
            copy_row.update(start=30,end=32.5)
            return [copy_row],{}
        with patch('karaoke_repeats.expand_repeats',side_effect=recover):
            recovered=waveform_repeat_hits(rows,selected,VOCAB,np.zeros(1),1)
        self.assertEqual(len(recovered),1)
        self.assertEqual(recovered[0]['text'],'GEL BANA')
        self.assertEqual(recovered[0]['start'],30)

    def test_waveform_only_prefix_is_rejoined_before_selecting_whole_refrain(self):
        from unittest.mock import patch
        rows=[{'id':'short','text':'GEL BANA','start':0,'end':0,'words':[]},
              {'id':'full','text':'GEL BANA,DON BURAYA','start':0,'end':0,'words':[]}]
        def find(_audio,row,_vocab,**_kwargs):
            if row['text']=='GEL BANA':return [hit(row['text'],1,3),hit(row['text'],10,12)]
            if row['text']=='DON BURAYA':return [hit(row['text'],15,17),hit(row['text'],35,37)]
            return []
        recovered={**hit('GEL BANA',30,32),'acoustic_repeat':True}
        audio=np.zeros((3000,len(VOCAB)),dtype='float32')
        with patch('karaoke_repeat_spotting.find_occurrences',side_effect=find),patch(
                'karaoke_repeat_spotting.waveform_repeat_hits',return_value=[recovered]):
            expanded,report,_=expand_supplied_rows(rows,audio,VOCAB,repeat_audio=(np.zeros(1),1))
        repeated=[r for r in expanded if r.get('repeat_source_id')=='full']
        self.assertEqual(len(repeated),1)
        self.assertEqual(repeated[0]['text'],rows[1]['text'])
        self.assertEqual((repeated[0]['start'],repeated[0]['end']),(30,37))
        self.assertEqual([w['word'] for w in repeated[0]['_occurrence_words']],rows[1]['text'].split())

    def test_shared_phrase_hit_is_repacked_for_each_supplied_comma_spacing(self):
        from unittest.mock import patch
        rows=[{'id':'short','text':'GEL BANA','start':0,'end':0,'words':[]},
              {'id':'spaced','text':'GEL BANA, CANIM BENIM','start':0,'end':0,'words':[]},
              {'id':'joined','text':'GEL BANA,CANIM BENIM','start':0,'end':0,'words':[]}]
        before=copy.deepcopy(rows)
        def find(_audio,row,_vocab,**_kwargs):
            if row['text']=='GEL BANA':return [hit('GEL BANA',1,3)]
            if row['text']=='GEL BANA, CANIM BENIM':return [hit(row['text'],10,15),hit(row['text'],20,25)]
            return []
        audio=np.zeros((3000,len(VOCAB)),dtype='float32')
        with patch('karaoke_repeat_spotting.find_occurrences',side_effect=find):
            expanded,_,_=expand_supplied_rows(rows,audio,VOCAB)
        self.assertEqual(rows,before)
        for row in expanded:
            if row['id'] in ('spaced','joined'):
                self.assertEqual([w['word'] for w in row['_occurrence_words']],row['text'].split())
        self.assertEqual(next(r for r in expanded if r['id']=='joined')['text'],rows[-1]['text'])

    def test_punctuation_parts_use_nearest_refrain_without_splitting_source(self):
        from karaoke_repeat_spotting import join_phrase_parts
        row={'id':'source','text':'GEL BANA, CANIM BENİM'}
        before=copy.deepcopy(row)
        left=[hit('GEL BANA',10,12),hit('GEL BANA',15,17)]
        right=[hit('CANIM BENİM',20,23)]
        joined=join_phrase_parts(row,left,right,VOCAB)
        self.assertEqual(row,before)
        self.assertEqual(len(joined),1)
        self.assertEqual((joined[0]['row_id'],joined[0]['text']),('source',row['text']))
        self.assertEqual(joined[0]['start'],15)
        self.assertEqual([w['word'] for w in joined[0]['words']],row['text'].split())
        self.assertEqual(joined[0]['words'][1]['end'],17)
        self.assertEqual(joined[0]['words'][2]['start'],20)

    def test_punctuation_parts_preserve_joined_user_token_and_real_pause(self):
        from karaoke_repeat_spotting import join_phrase_parts
        row={'id':'source','text':'GEL BANA,CANIM BENİM'}
        joined=join_phrase_parts(row,[hit('GEL BANA',10,12)],[hit('CANIM BENİM',15,18)],VOCAB)
        self.assertEqual([w['word'] for w in joined[0]['words']],row['text'].split())
        parts=joined[0]['words'][1]['timing_reference']['parts']
        self.assertEqual([w['word'] for w in parts],['BANA','CANIM'])
        self.assertEqual((parts[0]['end'],parts[1]['start']),(12,15))
        self.assertFalse(joined[0]['words'][1]['timing_reference']['acoustically_verified'])
        from karaoke_repeat_spotting import pack_occurrence_words
        restored=pack_occurrence_words({'text':'GEL BANA, CANIM BENİM'},joined[0]['words'],VOCAB)
        self.assertEqual([w['word'] for w in restored],['GEL','BANA,','CANIM','BENİM'])
        self.assertEqual((restored[1]['end'],restored[2]['start']),(12,15))

    def test_punctuation_parts_reject_music_gap_overlap_and_wrong_suffix(self):
        from karaoke_repeat_spotting import join_phrase_parts
        row={'id':'source','text':'GEL BANA, CANIM BENİM'}
        for suffix in [hit('CANIM BENİM',18,20),hit('CANIM BENİM',11,14),hit('BAŞKA SÖZ',14,16)]:
            self.assertEqual(join_phrase_parts(row,[hit('GEL BANA',10,12)],[suffix],VOCAB),[])

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
    def test_candidate_progress_advances_inside_row_without_changing_hits(self):
        from karaoke_repeat_spotting import find_occurrences
        audio=evidence(['gel bana','gel bana','gel bana'])
        row={'id':'a','text':'GEL BANA'};updates=[]
        expected=find_occurrences(audio,row,VOCAB)
        actual=find_occurrences(audio,row,VOCAB,progress=lambda p,m:updates.append((p,m)))
        self.assertEqual(expected,actual)
        self.assertGreater(len(updates),1)
        self.assertTrue(all(0<=p<=1 for p,_ in updates))
        self.assertGreater(updates[-1][0],updates[0][0])
        overall=[]
        expand_supplied_rows([row],audio,VOCAB,progress=lambda p,m:overall.append(p))
        self.assertEqual(overall,sorted(overall));self.assertEqual(overall[-1],1.)

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
    def test_weak_short_prefix_does_not_discard_first_verse_without_rival(self):
        rows=[{'id':'a','text':'LI WARGEHEN EVINE'},{'id':'b','text':'REWI ME IRO HEVAL'}]
        first=hit(rows[0]['text'],54.52,58.44)
        first['words'][0].update(end=54.62,probability=.30)
        chosen=select_occurrences(rows,[first,hit(rows[1]['text'],59.6,64.42),
            hit(rows[0]['text'],69.96,73.84),hit(rows[1]['text'],75.08,79.82)],VOCAB)
        self.assertEqual([round(h['start'],2) for h in chosen],[54.52,59.6,69.96,75.08])
        self.assertEqual([h['kind'] for h in chosen],['original','original','repeat','repeat'])
    def test_compound_refrain_is_split_and_existing_repeat_identity_is_preserved(self):
        from karaoke_supplied_alignment import prepare_supplied_rows
        rows=[{'id':'a','text':'Dil disoje','start':111.,'end':113.7,'words':[]},
              {'id':'auto-repeat:bad','repeat_source_id':'a','text':'Dil disoje','start':195.,'end':197.,'words':[]},
              {'id':'b','text':'Dil disoje,diqîre heval.','start':118.,'end':142.,'words':[]}]
        original=copy.deepcopy(rows);prepared=prepare_supplied_rows(rows)
        self.assertEqual([r['text'] for r in prepared],['Dil disoje','Dil disoje','Dil disoje','diqîre heval.'])
        self.assertEqual(len({r['id'] for r in prepared}),4)
        self.assertEqual(prepared[1],rows[1])
        self.assertEqual(prepare_supplied_rows(prepared),prepared)
        self.assertEqual(rows,original)
        rows[1]['locked']=True
        self.assertTrue(any(r['id']=='auto-repeat:bad' for r in prepare_supplied_rows(rows)))
        rows[2]['locked']=True
        self.assertEqual(prepare_supplied_rows(rows)[-1],rows[2])
    def test_refrain_pause_does_not_hide_repetitions_or_suffix(self):
        from karaoke_supplied_alignment import prepare_supplied_rows
        rows=[{'id':'a','text':'GEL BANA','start':0,'end':0,'words':[]},
              {'id':'b','text':'GEL BANA,DON BURAYA','start':0,'end':0,'words':[]}]
        sung=['gel bana','gel bana','gel bana','don buraya','gel bana','don buraya']
        silence=np.full((70,len(VOCAB)),-20,dtype='float32');silence[:,0]=0
        audio=np.concatenate([part for text in sung for part in (evidence([text]),silence)])
        expanded,report,hits=expand_supplied_rows(prepare_supplied_rows(rows),audio,VOCAB)
        self.assertEqual([r['text'].lower() for r in expanded],sung)
        self.assertEqual(len(hits),6)
    def test_verified_occurrence_replaces_displaced_whole_song_path_atomically(self):
        from karaoke_supplied_alignment import apply_occurrence_windows
        rows=[{'id':'a','text':'LI EVINE','words':[],
               '_occurrence_words':[{'word':'LI','start':54.52,'end':54.62,'probability':.3},
                                    {'word':'EVINE','start':54.7,'end':58.44,'probability':.9}]}]
        aligned=[{'word':'LI','start':16.7,'end':16.98},{'word':'EVINE','start':17.48,'end':58.44}]
        self.assertEqual(apply_occurrence_windows(aligned,rows,VOCAB,0,345),2)
        self.assertEqual([w['start'] for w in aligned],[54.52,54.7])
        rows[0]['locked']=True;before=copy.deepcopy(aligned)
        self.assertEqual(apply_occurrence_windows(aligned,rows,VOCAB,0,345),0)
        self.assertEqual(aligned,before)
    def test_waveform_copies_can_supply_occurrences_missing_from_ctc(self):
        from karaoke_repeat_spotting import waveform_repeat_hits
        rng=np.random.default_rng(15);phrase=rng.normal(0,.1,4000)
        audio=np.zeros(24000,dtype='float32');audio[2000:6000]=phrase;audio[14000:18000]=phrase
        rows=[{'id':'a','text':'GEL BANA'}]
        candidates=[hit('GEL BANA',1,3)]
        additions=waveform_repeat_hits(rows,candidates,VOCAB,audio,2000)
        self.assertEqual(len(additions),1);self.assertAlmostEqual(additions[0]['start'],7,places=2)
        self.assertTrue(additions[0]['acoustic_repeat'])
        self.assertEqual(additions[0]['words'][0]['timing_reference']['method'],'waveform_repeat_match')
    def test_borderline_occurrence_requires_independent_stronger_verification(self):
        from karaoke_repeat_spotting import find_occurrences
        audio=evidence(['gel bana']);labels=audio.argmax(axis=1)
        probabilities=np.full(audio.shape,.65/(len(VOCAB)-1),dtype='float32')
        probabilities[np.arange(len(audio)),labels]=.35
        weak=np.log(probabilities);row={'id':'a','text':'GEL BANA'};calls=[]
        self.assertEqual(find_occurrences(weak,row,VOCAB),[])
        def verify(row,a,b):
            calls.append((a,b));return hit(row['text'],a,b)['words']
        self.assertTrue(find_occurrences(weak,row,VOCAB,rescue=verify));self.assertTrue(calls)
        self.assertEqual(find_occurrences(weak,row,VOCAB,rescue=lambda *args:None),[])
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
