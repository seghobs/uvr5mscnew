"""Publish all inspected refinement outcomes, including rejected candidates."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.atlas_benchmark import write_json


def export():
    experiments=[]
    for name in ['atlas_refinement','atlas_refinement_2','atlas_refinement_conservative',
                 'atlas_resurrection','atlas_resurrection_six','atlas_resurrection_six_warm','atlas_confirmation']:
        folder=ROOT/'cache'/name
        path=folder/'evaluation.json'
        if not path.exists():continue
        r=json.loads(path.read_text(encoding='utf8'))
        experiments.append({'id':name,'accepted':r['accepted'],'development_count':len(r['manifest']['development']),
            'evaluation_count':len(r['rows']),'comparisons':r['comparisons'],'summary':r['summary'],
            'limitations':r['limitations'],'models':r['manifest']['models'],
            'report_sha256':__import__('hashlib').sha256(path.read_bytes()).hexdigest()})
    report={'experiments':experiments,'final_confirmation_opened':(ROOT/'cache/atlas_confirmation/evaluation.json').exists(),
        'cancelled_optimizer_runs':['atlas_refinement_3','atlas_refinement_relative','atlas_resurrection'],
        'note':'Stopped optimizers are not successful or failed audio evaluations. Previously inspected recordings become DEVELOPMENT in later experiments. No zero-loss claim.'}
    write_json(ROOT/'docs/atlas-studio-v2-refinement-attempts.json',report)
    lines=['# Atlas V2 iyileştirme deneyleri','',
        'Başarısız adaylar da burada raporlanır. Bir önceki deneyde incelenen kayıtlar sonraki deneylerde geliştirme verisidir; yeni doğrulama yerine sunulmaz.','',
        '| Deney | Geliştirme / doğrulama | V1 SDR farkı | Mevcut V2 SDR farkı | Kabul |',
        '|---|---:|---:|---:|---|']
    for r in experiments:
        lines.append(f"| {r['id']} | {r['development_count']} / {r['evaluation_count']} | {r['comparisons']['v1']['mean_sdr_delta_db']:+.4f} dB | {r['comparisons']['current']['mean_sdr_delta_db']:+.4f} dB | {'Evet' if r['accepted'] else 'Hayır'} |")
    lines.extend(['','Kabul için V1 ve mevcut V2 karşısında pozitif ortalama SDR kazancı ve pozitif %95 eşleştirilmiş bootstrap alt sınırı gerekir. İki kanalın ortalama SI-SDR ve dört eksik/fazla spektral içerik göstergesinin tamamı iki sürümden de kötüleşmemelidir. 0,2 dB ayrıca hedef olarak raporlanır.',
        '', 'Spektral göstergeler gerçek sızıntı yüzdesi değildir. Kısa referans kayıtlarındaki ortalamalar her şarkıda üstünlük veya Türkçe tam şarkılarda sıfır kayıp kanıtlamaz.',
        '', 'Yakınsamayan optimizasyonlar durduruldu; ses kalite testinden geçmiş sayılmaz. Yeni enstrümantal uzmanın ilk denemesinde hatalı kanal etiketleri tespit edildi; bu çıktılar silinerek doğru etiketlerle yeniden üretildi ve karışım eğitimine alınmadı.',
        '', f"Son 10 kayıtta doğrulama: {'Açıldı; ayrıntılar JSON raporunda.' if report['final_confirmation_opened'] else 'Henüz açılmadı.'}"])
    (ROOT/'docs/atlas-studio-v2-refinement-attempts.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print('Exported',len(experiments),'completed evaluations')


if __name__=='__main__':export()
