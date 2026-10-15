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

    def test_unsupported_language_is_not_run_with_turkish(self):
        with self.assertRaises(ValueError):resolve_language('de',[{'text':'Guten Tag'}])
        with self.assertRaises(ValueError):model_spec('de')


if __name__=='__main__':unittest.main()
