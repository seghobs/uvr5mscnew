import unittest
from karaoke_design import soft_word_events,row_motion,lead_cue_events

class LayoutTests(unittest.TestCase):
    def test_render_sweep_uses_measured_glyph_bounds(self):
        from karaoke_design import prepare_word_geometry
        import re
        row={'start':0,'end':3,'text':'YERE SÜRÜLDÜ YÜZÜMÜZ','words':[
            {'word':w,'start':i,'end':i+1,'timing_source':'ctc'} for i,w in enumerate('YERE SÜRÜLDÜ YÜZÜMÜZ'.split())]}
        geometry=prepare_word_geometry([row],1920,1080,550,76)[0]
        if geometry is None:self.skipTest('Windows Segoe font required')
        events=soft_word_events(row,4,1920,1080,550,76,'neon',geometry=geometry)
        first=next(e for e in events if e.startswith('Dialogue: 2'))
        clip=re.search(r'\\clip\(([^)]+)\)',first).group(1).split(',')
        self.assertEqual(float(clip[0]),geometry['boxes'][0][0])
        self.assertEqual(float(clip[1]),geometry['ink_top'])
        self.assertEqual(len(geometry['boxes']),3)
        repeated=prepare_word_geometry([{**row,'start':10,'end':13}],1920,1080,550,76)[0]
        self.assertEqual(repeated,geometry)

    def test_each_row_restarts_its_own_vertical_gradient(self):
        import re
        row={'start':1,'end':2,'text':'TEST','words':[{'word':'TEST','start':1,'end':2,'timing_source':'ctc'}]}
        a=soft_word_events(row,3,1920,1080,550,76,'gold')
        b=soft_word_events(row,3,1920,1080,720,76,'gold')
        if a is None:self.skipTest('Windows Segoe font required')
        aa=next(e for e in a if e.startswith('Dialogue: 2'))
        bb=next(e for e in b if e.startswith('Dialogue: 2'))
        self.assertIn(',474.00,',aa)
        self.assertIn(',644.00,',bb)
        self.assertEqual(re.findall(r'\\1c&H([0-9A-F]+)&',aa),re.findall(r'\\1c&H([0-9A-F]+)&',bb))

    def test_exit_shrinks_after_last_word_not_during_its_fill(self):
        row={'start':1,'end':2,'text':'TEST','words':[{'word':'TEST','start':1,'end':2,'timing_source':'ctc'}]}
        motion=row_motion(row,next_start=2.1)
        self.assertEqual(motion['shrink'],2)
        events=soft_word_events(row,3,1920,1080,550,76,'gold',motion)
        if events is None:self.skipTest('Windows Segoe font required')
        self.assertTrue(any(r'\fscy65)' in e for e in events))

    def test_soft_front_reaches_completed_clip_without_a_color_jump(self):
        import re
        row={'start':1,'end':2,'text':'BERABERCE','words':[{'word':'BERABERCE','start':1,'end':2,'timing_source':'ctc'}]}
        events=soft_word_events(row,3,1920,1080,550,76,'gold')
        if events is None:self.skipTest('Windows Segoe font required')
        sweeps=[e for e in events if r'\alpha&H' in e]
        self.assertEqual(len(sweeps),17*16)
        core=sweeps[0];completed=events[-16]
        self.assertEqual(re.findall(r'\\clip\(([^)]+)\)',core)[-1],re.findall(r'\\clip\(([^)]+)\)',completed)[-1])
        self.assertEqual(len(set(re.findall(r'\\1c&H([0-9A-F]+)&',''.join(sweeps)))),16)

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

