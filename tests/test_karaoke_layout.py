import unittest
from karaoke_design import soft_word_events,row_motion

class LayoutTests(unittest.TestCase):
    def test_handoff_enters_before_voice_and_preserves_word_clock(self):
        import copy
        old={'start':155.5,'end':160.7,'text':'HEY','words':[{'word':'HEY','start':159.82,'end':160.7,'timing_source':'ctc'}]}
        new={'start':160.98,'end':163.78,'text':'GÖNÜL','words':[{'word':'GÖNÜL','start':160.98,'end':161.52,'timing_source':'ctc'}]}
        original=copy.deepcopy(new)
        motion=row_motion(new)
        self.assertAlmostEqual(motion['enter'],160.74)
        self.assertGreater(row_motion(old,next_start=new['start'])['end'],new['start'])
        events=soft_word_events(new,164,1920,1080,550,76,'neon',motion)
        self.assertEqual(new,original)
        if events is None:self.skipTest('Windows Segoe font required')
        self.assertIn('0:02:40.74,0:02:40.98',events[0])
        self.assertIn(r'\move(960.0,390,960.0,550,0,240)',events[0])
        self.assertTrue(any(event.startswith('Dialogue: 2,0:02:40.98,') for event in events))
        self.assertFalse(any(event.startswith('Dialogue: 2,0:02:40.74,') for event in events))

    def test_heading_is_saved_with_its_song_project(self):
        from local_projects import ProjectStore
        from pathlib import Path
        import tempfile
        self.assertEqual(ProjectStore.identity('uvr-video-heading:song.wav'),'song.wav')
        with tempfile.TemporaryDirectory() as directory:
            store=ProjectStore(Path(directory))
            store.put('uvr-video-heading:song.wav','edited title')
            store.put('uvr-video-heading:other.wav','keep')
            reopened=ProjectStore(Path(directory))
            self.assertEqual(reopened.get('uvr-video-heading:song.wav'),'edited title')
            self.assertEqual(reopened.get('uvr-video-heading:other.wav'),'keep')

    def test_all_words_share_one_centered_line_and_normal_spacing(self):
        row={'start':1,'end':3,'text':'BİZİ ANLAR','words':[{'word':'BİZİ','start':1,'end':2},{'word':'ANLAR','start':2,'end':3}]}
        events=soft_word_events(row,3.5,1920,1080,550,76,'neon')
        if events is None:self.skipTest('Windows Segoe font required')
        self.assertTrue(all(r'\an2\pos(960.000,550)' in event for event in events))
        self.assertTrue(all(event.endswith('BİZİ ANLAR') for event in events))
        self.assertEqual(sum(event.startswith('Dialogue: 1,') for event in events),1)

