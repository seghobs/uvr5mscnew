import unittest
from karaoke_design import soft_word_events,row_motion,lead_cue_events

class LayoutTests(unittest.TestCase):
    def test_soft_front_reaches_completed_clip_without_a_color_jump(self):
        import re
        row={'start':1,'end':2,'text':'BERABERCE','words':[{'word':'BERABERCE','start':1,'end':2,'timing_source':'ctc'}]}
        events=soft_word_events(row,3,1920,1080,550,76,'gold')
        if events is None:self.skipTest('Windows Segoe font required')
        sweeps=[e for e in events if r'\alpha&H' in e]
        self.assertEqual(len(sweeps),17)
        core=sweeps[0];completed=events[-1]
        self.assertEqual(re.findall(r'\\clip\(([^)]+)\)',core)[-1],re.findall(r'\\clip\(([^)]+)\)',completed)[-1])
        self.assertIn(r'\t(0,1000,\1c&H0098FF&)',core)

    def test_preparation_cue_does_not_touch_word_onsets(self):
        events=lead_cue_events(10,20,1920,390,'gold')
        self.assertIn('0:00:17.00,0:00:19.52',events[0])
        self.assertEqual(sum('HAZIRLAN' in e for e in events),3)
        self.assertEqual(lead_cue_events(19.8,20,1920,390,'gold'),[])

    def test_handoff_enters_before_voice_and_preserves_word_clock(self):
        import copy
        old={'start':155.5,'end':160.7,'text':'HEY','words':[{'word':'HEY','start':159.82,'end':160.7,'timing_source':'ctc'}]}
        new={'start':160.98,'end':163.78,'text':'GÖNÜL','words':[{'word':'GÖNÜL','start':160.98,'end':161.52,'timing_source':'ctc'}]}
        original=copy.deepcopy(new)
        motion=row_motion(new)
        self.assertAlmostEqual(motion['enter'],160.50)
        self.assertGreater(row_motion(old,next_start=new['start'])['end'],new['start'])
        events=soft_word_events(new,164,1920,1080,550,76,'neon',motion)
        self.assertEqual(new,original)
        if events is None:self.skipTest('Windows Segoe font required')
        self.assertIn('0:02:40.50,0:02:40.98',events[0])
        self.assertIn(r'\move(960.0,390,960.0,550,0,480)',events[0])
        self.assertTrue(any(event.startswith('Dialogue: 2,0:02:40.98,') for event in events))
        self.assertFalse(any(event.startswith('Dialogue: 2,0:02:40.50,') for event in events))

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

