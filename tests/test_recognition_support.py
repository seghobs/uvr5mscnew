import copy
import unittest
from unittest.mock import patch

from karaoke_recognition_support import supported_word,apply_recognition_support,review_windows,recover_recognition_reviews


class RecognitionSupportTests(unittest.TestCase):
    def test_unsupported_whisper_language_is_explicitly_skipped(self):
        from types import SimpleNamespace
        rows=[{'text':'KURMANCÎ','start':1,'end':2,'words':[{'word':'KURMANCÎ','start':1,'end':2,'needs_review':True}]}]
        with patch('soundfile.info',return_value=SimpleNamespace(duration=20)):
            result=recover_recognition_reviews('song.wav',None,rows,lambda _:self.fail('unsupported model must not run'),{},lambda *a:None,'kmr')
        self.assertEqual(result['recognition_skipped_reason'],'whisper_language_not_supported')
    def test_automatic_retry_uses_unprompted_recognition_and_installed_models(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        import numpy as np
        import soundfile as sf
        rows=[{'id':'a','text':'ANLAMAZ','start':10.,'end':10.2,'words':[self.word()]}]
        calls=[]
        class Model:
            def transcribe(self,audio,**options):
                calls.append(options)
                return [SimpleNamespace(words=[SimpleNamespace(word='anlamaz',start=.8,end=1.5,probability=.95)])],None
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'vocal.wav';sf.write(path,np.zeros((320000,2),dtype='float32'),16000)
            with patch('pathlib.Path.is_file',return_value=True):
                evidence=[{**self.phonetic(model),'start':10.,'end':10.7,'audio_source':'vocals','channel':'left'} for model in ('tr','tr_cv8')]
                diagnostics={'model_crosscheck_candidates':[{'row_id':'a','word_index':0,'candidates':evidence}]}
                result=recover_recognition_reviews(path,None,rows,lambda _:Model(),diagnostics,lambda *a:None,'tr')
        self.assertEqual(result['recognition_repaired_words'],1)
        self.assertFalse(rows[0]['words'][0]['needs_review'])
        self.assertTrue(calls)
        self.assertTrue(all(x['condition_on_previous_text'] is False and 'initial_prompt' not in x for x in calls))

    def test_unlocated_words_do_not_trigger_unbounded_whole_song_search(self):
        row={'text':'HA','start':0,'end':0,'words':[{'word':'HA','start':0,'end':0,'needs_review':True}]}
        self.assertEqual(review_windows([row],300),([],1))

    def test_retry_windows_are_limited_and_preserve_silence(self):
        rows=[{'text':'SON','start':i*40+1,'end':i*40+2,'words':[{'word':'SON','start':i*40+1,'end':i*40+2,'needs_review':True}]} for i in range(20)]
        windows,skipped=review_windows(rows,800)
        self.assertEqual(len(windows),12);self.assertEqual(skipped,8)
        self.assertTrue(all(b-a<=35 for a,b in windows))
    def word(self):
        return dict(word='ANLAMAZ',start=10.,end=10.2,probability=.2,timing_source='ctc',needs_review=True)

    def recognition(self,source='vocals',model='large-v3'):
        return dict(word='anlamaz.',start=9.7,end=11.8,probability=.97,model=model,source=source)

    def phonetic(self,model='tr'):
        return dict(word='ANLAMAZ',start=10.,end=11.8,probability=.42,model=model,source='vocals',channel='left')

    def test_lexical_evidence_and_two_models_can_verify_a_held_word(self):
        old=self.word()
        fixed=supported_word(old,[self.phonetic(),self.phonetic('tr_cv8')],[self.recognition()],9.9,12)
        self.assertFalse(fixed['needs_review'])
        self.assertEqual(fixed['word'],old['word'])
        self.assertEqual(fixed['probability'],.42,'do not manufacture a higher CTC score')
        self.assertEqual(fixed['end'],11.8)

    def test_recognition_needs_independent_observations(self):
        old=self.word();a=self.recognition();b=self.recognition('original','large-v3-turbo')
        # Direct recognition fits only when it respects the neighbouring words.
        self.assertIs(supported_word(old,[],[a,b],10.,12),old)
        self.assertIs(supported_word(old,[],[a,b],9.,12),old,'even two recognizers cannot certify fine timing without phonetic evidence')
        self.assertIs(supported_word(old,[],[a,copy.deepcopy(a)],9.,12),old)
        self.assertIs(supported_word(old,[],[a,self.recognition('original')],9.,12),old,'two views of one recognizer are not independent models')

    def test_forced_candidates_alone_wrong_text_and_distant_hallucinations_are_rejected(self):
        for kind in ('absent','wrong','distant','weak','same_model'):
            old=self.word();a,b=self.phonetic(),self.phonetic('tr_cv8');r=self.recognition()
            if kind=='wrong':r['word']='ANLATMAZ'
            if kind=='distant':r.update(start=100,end=102)
            if kind=='weak':a['probability']=b['probability']=.1
            if kind=='same_model':b['model']='tr'
            fixed=supported_word(old,[a,b],[] if kind=='absent' else [r],9.9,12)
            self.assertIs(fixed,old,kind)

    def test_manual_and_locked_words_survive_recognition(self):
        for kind in ('manual','locked'):
            w=self.word();row=dict(id='a',text=w['word'],start=10,end=10.2,words=[w])
            if kind=='manual':w['timing_source']='manual'
            else:row['locked']=True
            before=copy.deepcopy(row)
            repairs=apply_recognition_support([row],{(0,0):[self.phonetic(),self.phonetic('tr_cv8')]},
                [self.recognition(),self.recognition('original')],20)
            self.assertEqual(repairs,[]);self.assertEqual(row,before)


if __name__=='__main__':unittest.main()
