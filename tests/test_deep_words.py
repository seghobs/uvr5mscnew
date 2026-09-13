import unittest
from karaoke_deep_words import rank_candidates,normalized,filter_english_adlibs

class DeepWordsTests(unittest.TestCase):
    def test_english_adlibs_removed_without_shifting_turkish(self):
        labels=['OKEY!', 'TOZ', 'PEMBE', 'YES,', 'HİSLERLE', 'İ', 'LOVE', 'YOU']
        words=[{'word':label,'start':i,'end':i+.5,'needs_review':True} for i,label in enumerate(labels)]
        kept,rejected=filter_english_adlibs(words)
        self.assertEqual([w['word'] for w in kept],['TOZ','PEMBE','HİSLERLE'])
        self.assertEqual([w['start'] for w in kept],[1,2,4])
        self.assertEqual(rejected,['OKEY!','YES,','İ','LOVE','YOU'])
        self.assertEqual([w['word'] for w in words],labels)
    def test_english_only_candidate_becomes_empty(self):
        kept,_=filter_english_adlibs([{'word':s,'start':i,'end':i+.5} for i,s in enumerate(['OKAY','YEAH','YES'])])
        self.assertEqual(kept,[])
    def test_turkish_homographs_and_substrings_preserved(self):
        labels=['HEY','CAN','OF','ON','YESTER','TAMAM','SEVGİLİM']
        words=[{'word':s,'start':i,'end':i+.5} for i,s in enumerate(labels)]
        self.assertEqual(filter_english_adlibs(words),(words,[]))
    def test_agreement_not_probability_alone(self):
        candidates=[{'text':'KARA KARA SENİ','probability':.6},{'text':'kara kara seni','probability':.7},{'text':'ALTYAZI','probability':.999}]
        result=rank_candidates(candidates)
        self.assertEqual(result[0]['text'],'kara kara seni')
        self.assertTrue(all(c['needs_review'] for c in result))
        self.assertEqual(normalized('KARA KARA SENİ'),'kara kara seni')
    def test_single_candidate_is_not_consensus(self):
        self.assertEqual(rank_candidates([{'text':'BİR','probability':.99}])[0]['agreement'],0)

if __name__=='__main__':unittest.main()
