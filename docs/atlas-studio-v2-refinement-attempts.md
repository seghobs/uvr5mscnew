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
