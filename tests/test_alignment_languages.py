import unittest
from karaoke_alignment_models import AlignmentVocabulary, resolve_language, model_spec
from karaoke_ctc import acoustic_text, supported_targets


class LanguageTests(unittest.TestCase):
    def test_kurmanji_preserves_vowel_distinctions_and_uppercase_i(self):
        vocab=AlignmentVocabulary({c:i for i,c in enumerate('abcdefghijklmnopqrstuvwxyzêîûçş|')},'kmr')
        self.assertEqual([acoustic_text(t,vocab) for t in ['DIL','DİL','VÊ','DÎN','Û','XEW']],
                         ['dil','dil','vê','dîn','û','xew'])
        self.assertEqual(supported_targets([{'word':'VÊ'},{'word':'世界'},{'word':'XEW'}],vocab)[0],[0,2])

    def test_turkish_normalization_and_model_are_unchanged(self):
        from karaoke_ctc import MODEL_DIR,MODEL_ID,MODEL_REVISION
        vocab=AlignmentVocabulary({c:i for i,c in enumerate('abcdefghijklmnopqrstuvwxyzçöüğış|')},'tr')
        self.assertEqual(acoustic_text('IŞIK',vocab),'ışık')
        self.assertEqual(acoustic_text('İYİ',vocab),'iyi')
        self.assertEqual(acoustic_text('ÂŞIK',vocab),'aşık')
        self.assertEqual(model_spec('tr'),(MODEL_DIR,MODEL_ID,MODEL_REVISION))

    def test_explicit_language_wins_and_aliases_resolve(self):
        rows=[{'text':'EZ TU Jİ VÊ XEW Û DÎN'}]
        self.assertEqual(resolve_language('tr',rows),'tr')
        for code in ['ku','kur','kmr','KMR']:
            self.assertEqual(resolve_language(code,[]),'kmr')
        self.assertEqual(resolve_language('auto',rows),'kmr')
        self.assertEqual(resolve_language('auto',[{'text':'GÖNÜL GENE BU GECE KARA YAZIMIZ'}]),'tr')
        self.assertEqual(resolve_language('auto',[{'text':'ÂŞIK DİL YÂRİ ARAR'}]),'tr')
        self.assertEqual(resolve_language('auto',[{'text':'TU'}]),'tr')

    def test_azerbaijani_and_english_targets_and_detection(self):
        az=AlignmentVocabulary({c:i for i,c in enumerate('abcdefghijklmnopqrstuvwxyzəçöüğış|')},'az')
        self.assertEqual(acoustic_text('SƏNİN EŞQİN',az),'sənin eşqin')
        self.assertEqual(supported_targets([{'word':t} for t in 'SƏNİN EŞQİN MƏNİ DÜŞÜRDÜ DİLƏ'.split()],az)[0],list(range(5)))
        en=AlignmentVocabulary({c:i for i,c in enumerate('abcdefghijklmnopqrstuvwxyz|')},'en')
        self.assertEqual(acoustic_text('I MISS YOU',en),'i miss you')
        self.assertEqual(resolve_language('auto',[{'text':'SƏNİN EŞQİN MƏNİ'}]),'az')
        self.assertEqual(resolve_language('auto',[{'text':'THE LOVE OF MY LIFE AND YOU'}]),'en')
        self.assertEqual(resolve_language('en',[{'text':'SƏNİN'}]),'en')
        for alias in ('az','aze','azj'):self.assertEqual(resolve_language(alias,[]),'az')
        for alias in ('en','eng'):self.assertEqual(resolve_language(alias,[]),'en')
        from karaoke_alignment_models import MMS_ADAPTERS
        self.assertEqual(MMS_ADAPTERS['az'],'azj-script_latin')
        self.assertEqual(MMS_ADAPTERS['en'],'eng')
        self.assertEqual(model_spec('az'),model_spec('en'))

    def test_unsupported_language_is_not_run_with_turkish(self):
        with self.assertRaises(ValueError):resolve_language('de',[{'text':'Guten Tag'}])
        with self.assertRaises(ValueError):model_spec('de')


if __name__=='__main__':unittest.main()
