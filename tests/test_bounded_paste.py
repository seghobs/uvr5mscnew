import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import paste_sync


class BoundedPasteTests(unittest.TestCase):
    def test_four_timeouts_keep_all_lines(self):
        with patch('paste_sync.subprocess.run',side_effect=subprocess.TimeoutExpired('worker',15)) as run:
            rows,report=paste_sync.synchronize('unused.wav','Bir\nİki')
        self.assertEqual(run.call_count,4)
        self.assertTrue(all(call.kwargs['timeout']==15 for call in run.call_args_list))
        self.assertEqual(report['attempts'],4)
        self.assertEqual(report['pending'],[1,2])
        self.assertEqual([r['text'] for r in rows],['Bir','İki'])

    def test_success_stops_early(self):
        def recognize(args,**kwargs):
            Path(args[-1]).write_text(json.dumps([{'words':[{'word':'Bir','start':2,'end':3}]}]))
        with patch('paste_sync.subprocess.run',side_effect=recognize) as run:
            rows,report=paste_sync.synchronize('unused.wav','Bir')
        self.assertEqual(run.call_count,1)
        self.assertEqual(report['pending'],[])
        self.assertEqual(rows[0]['start'],2)

    def test_failed_later_attempts_preserve_partial_match(self):
        calls=0
        def recognize(args,**kwargs):
            nonlocal calls
            calls+=1
            if calls>1:raise subprocess.CalledProcessError(1,args)
            Path(args[-1]).write_text(json.dumps([{'words':[{'word':'Bir','start':2,'end':3}]}]))
        with patch('paste_sync.subprocess.run',side_effect=recognize):
            rows,report=paste_sync.synchronize('unused.wav','Bir\nİki')
        self.assertEqual(report['attempts'],4)
        self.assertEqual(report['pending'],[2])
        self.assertEqual(rows[0]['start'],2)

    def test_real_hanging_child_is_terminated(self):
        actual_run=subprocess.run
        def hanging_child(args,**kwargs):
            return actual_run([sys.executable,'-c','import time; time.sleep(30)'],timeout=.1,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        with patch('paste_sync.subprocess.run',side_effect=hanging_child) as run:
            rows,report=paste_sync.synchronize('unused.wav','Bir')
        self.assertEqual(run.call_count,4)
        self.assertEqual(report['pending'],[1])
        self.assertEqual(rows[0]['text'],'Bir')


if __name__=='__main__':unittest.main()
