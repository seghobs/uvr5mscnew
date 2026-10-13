import copy
import unittest
import numpy as np
from karaoke_interludes import place_interludes,generated,regions
from karaoke_supplied_alignment import alignment_mono
from karaoke_timing import render_windows,solo_windows


class InterludeTests(unittest.TestCase):
    def setUp(self):
        self.rows=[{'id':'one','text':'İLK KITA','start':10,'end':20},
                   {'id':'two','text':'İKİNCİ KITA','start':40,'end':50}]

    def test_intro_interlude_and_outro_only_with_music_evidence(self):
        old=copy.deepcopy(self.rows)
        result,report=place_interludes(self.rows,60,[],[(0,60)])
        self.assertEqual(report['solo_count'],3)
        self.assertEqual([(r['start'],r['end']) for r in result if generated(r)],[(0,10),(20,40),(50,60)])
        self.assertEqual(self.rows,old)
        self.assertEqual([r for r in result if not generated(r)],self.rows)
        for row in result:
            if generated(row):self.assertEqual((row['words'][0]['start'],row['words'][0]['end']),(row['start'],row['end']))

    def test_time_gap_without_music_and_short_pause_get_no_label(self):
        result,report=place_interludes(self.rows,60,[],[])
        self.assertEqual(result,self.rows);self.assertEqual(report['solo_count'],0)
        close=[self.rows[0],{**self.rows[1],'start':22}]
        _,report=place_interludes(close,50,[],[(20,22)])
        self.assertEqual(report['solo_count'],0)

    def test_unlisted_voice_and_held_vowels_veto_solo(self):
        result,_=place_interludes(self.rows,50,[(20,25),(30,35)],[(20,40)])
        labels=[r for r in result if generated(r)]
        for row in labels:
            self.assertFalse(any(row['start']<b and row['end']>a for a,b in [(20,25),(30,35)]))
        self.assertGreaterEqual(labels[0]['start'],25.2)

    def test_locked_label_and_words_unchanged(self):
        locked={'id':'locked','text':'SOLO...','start':20,'end':40,'locked':True,
                'words':[{'word':'SOLO...','start':20,'end':40,'timing_source':'manual'}]}
        result,report=place_interludes([self.rows[0],locked,self.rows[1]],50,[],[(20,40)])
        self.assertEqual(result[1],locked);self.assertEqual(report['solo_count'],0)

    def test_rerun_has_same_labels_without_duplicates(self):
        result,_=place_interludes(self.rows,60,[],[(0,60)])
        repeated,_=place_interludes(result,60,[],[(0,60)])
        self.assertEqual(result,repeated)

    def test_fragmented_music_gap_gets_one_caption_without_bridging_voice(self):
        result,report=place_interludes(self.rows,50,[(24,25),(30,31)],[(20,40)])
        labels=[r for r in result if generated(r)]
        self.assertEqual(len(labels),1)
        self.assertEqual(report['solo_count'],1)
        self.assertAlmostEqual(labels[0]['start'],31.2)
        self.assertFalse(any(labels[0]['start']<b and labels[0]['end']>a for a,b in [(24,25),(30,31)]))
        again,_=place_interludes(result,50,[(24,25),(30,31)],[(20,40)])
        self.assertEqual(result,again)

    def test_multiple_unlocked_supplied_solo_labels_in_one_gap_collapse(self):
        labels=[{'id':str(i),'text':'SOLO...','start':20+i*4,'end':24+i*4} for i in range(4)]
        result,report=place_interludes([self.rows[0],*labels,self.rows[1]],50,[],[(20,40)])
        solos=[r for r in result if r['text']=='SOLO...']
        self.assertEqual(len(solos),1)
        self.assertEqual((solos[0]['start'],solos[0]['end']),(20,40))
        self.assertEqual(report['unplaced_solo_ids'],['1','2','3'])

    def test_stereo_cancellation_does_not_erase_the_vocal(self):
        t=np.linspace(-1,1,400,dtype=np.float32);audio=np.stack([t,-t],axis=1)
        np.testing.assert_equal(alignment_mono(audio),t)
        same=np.stack([t,t],axis=1);np.testing.assert_equal(alignment_mono(same),t)

    def test_regions_keep_absolute_time_and_bridge_only_short_holes(self):
        self.assertEqual(regions([True]*10+[False]*5+[True]*10),[[0,.5]])

    def test_video_uses_exact_solo_end_without_inventing_more_solos(self):
        solo={'text':'SOLO...','start':0,'end':9.5,'alignment_mode':'supplied_ctc'}
        lyric={'text':'SÖZ','start':10,'end':12,'alignment_mode':'supplied_ctc'}
        self.assertEqual(render_windows([solo,lyric])[0][1],9.5)
        self.assertEqual(solo_windows([solo,lyric],30),[])


if __name__=='__main__':unittest.main()
