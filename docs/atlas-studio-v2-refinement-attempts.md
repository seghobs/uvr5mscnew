# Atlas V2 iyileştirme deneyleri

Başarısız adaylar da burada raporlanır. Bir önceki deneyde incelenen kayıtlar sonraki deneylerde geliştirme verisidir; yeni doğrulama yerine sunulmaz.

| Deney | Geliştirme / doğrulama | V1 SDR farkı | Mevcut V2 SDR farkı | Kabul |
|---|---:|---:|---:|---|
| atlas_refinement | 32 / 8 | -0.0067 dB | -0.0042 dB | Hayır |
| atlas_refinement_2 | 40 / 8 | +0.1207 dB | +0.0834 dB | Hayır |
| atlas_refinement_conservative | 48 / 8 | +0.0448 dB | +0.0227 dB | Hayır |
| atlas_resurrection_six_warm | 56 / 8 | +0.4520 dB | +0.3890 dB | Evet |
| atlas_confirmation | 56 / 10 | +0.5317 dB | +0.4435 dB | Evet |

Kabul için V1 ve mevcut V2 karşısında pozitif ortalama SDR kazancı ve pozitif %95 eşleştirilmiş bootstrap alt sınırı gerekir. İki kanalın ortalama SI-SDR ve dört eksik/fazla spektral içerik göstergesinin tamamı iki sürümden de kötüleşmemelidir. 0,2 dB ayrıca hedef olarak raporlanır.

Spektral göstergeler gerçek sızıntı yüzdesi değildir. Kısa referans kayıtlarındaki ortalamalar her şarkıda üstünlük veya Türkçe tam şarkılarda sıfır kayıp kanıtlamaz.

Yakınsamayan optimizasyonlar durduruldu; ses kalite testinden geçmiş sayılmaz. Yeni enstrümantal uzmanın ilk denemesinde hatalı kanal etiketleri tespit edildi; bu çıktılar silinerek doğru etiketlerle yeniden üretildi ve karışım eğitimine alınmadı.

Son 10 kayıtta doğrulama: Açıldı; ayrıntılar JSON raporunda.

## 10 Ekim 2026: güncel altı modelli V2 üzerinde ek SDR optimizasyonu

Üç ek model için 12 karışım 24 geliştirme kaydında tarandı. SDR kazancı pozitif iki karışımın tam içerik kontrolleri de geçmedi. Güncel V2’ye karşı 56 geliştirme kaydında üç korumalı frekans ağırlığı optimizasyonu yapıldı; iki aday geliştirme kontrollerini geçti. En yüksek geliştirme SDR’sine sahip aday, doğrulama sonuçları açılmadan sabitlendi.

Sekiz daha önce kullanılmamış referans kaydında altı model yeniden çalıştırıldı (48 ayrıştırma). Veri setinin train/test etiketleri bu deneyin geliştirme/doğrulama ayrımından farklıdır; model eğitimiyle örtüşme bilinmez.

| Doğrulama ölçümü | Güncel V2 | Yeni aday |
|---|---:|---:|
| Vokal SDR (dB) | 12.085417 | 12.090094 |
| Vokal SI-SDR (dB) | 11.648200 | 11.652414 |
| Vokal eksik içerik göstergesi | 0.058700 | 0.058757 |
| Vokal fazla içerik göstergesi | 0.005720 | 0.005697 |
| Enstrümantal SDR (dB) | 16.017437 | 16.022114 |
| Enstrümantal SI-SDR (dB) | 15.888475 | 15.893296 |
| Enstrümantal eksik içerik göstergesi | 0.010235 | 0.010221 |
| Enstrümantal fazla içerik göstergesi | 0.004658 | 0.004660 |

Ortalama SDR farkı **+0.004676 dB**, %95 eşleştirilmiş bootstrap aralığı **[-0.000016, 0.010107] dB**; 6/8 kayıtta artış. Vokal eksik içerik ve enstrümantal fazla içerik göstergeleri kötüleşti. **Aday reddedildi; uygulamadaki preset değiştirilmedi.**

İçerik korumaları kaldırılarak yapılan ayrı geliştirme denemesi +0,165264 dB kazandı; vokal SI-SDR’si düştü, vokal fazla içerik ve enstrümantal eksik içerik göstergeleri arttı. Salt SDR’yi yükseltmenin iki kanalın kalitesini birlikte iyileştirmediği bu denemede görüldü.

SDR yüzde değildir; hatasız ayrımda örnek hata enerjisi sıfıra, SDR ise sonsuza gider. İçerik göstergeleri sızıntı yüzdesi olarak yorumlanmamalıdır. Türkçe tam kayıtlar gerçek stüdyo kanalları olmadan SDR referansı değildir.

[Ağırlıklar, kayıt bazında sonuçlar ve deney koşulları](atlas-studio-v2-sdr-optimization.json). Araçlar: `tools/atlas_sdr_optimize.py`, `tools/atlas_sdr_pool.py`, `tools/atlas_sdr_relaxed.py`, `tools/atlas_sdr_validate.py infer|evaluate`. Test: `env/python.exe -m unittest tests.test_atlas_sdr_optimize tests.test_atlas_refinement tests.test_atlas_band_ensemble tests.test_atlas_studio_v2` (18 test).
