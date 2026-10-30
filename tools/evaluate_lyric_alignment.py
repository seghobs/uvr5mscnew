"""Evaluate one exact recording, without modifying lyrics or audio."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from karaoke_alignment_benchmark import score_alignment

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',required=True,type=Path)
    parser.add_argument('--prediction',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--tolerance',type=float,default=.08)
    args=parser.parse_args()
    report=score_alignment(json.loads(args.reference.read_text(encoding='utf8')),
                           json.loads(args.prediction.read_text(encoding='utf8')),args.tolerance)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))
