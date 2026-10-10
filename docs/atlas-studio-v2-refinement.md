# Atlas Studio V2: son iyileştirme doğrulaması

Karar: **Kabul edildi**. 6 model; 56 geliştirme kaydı, 10 ayrı doğrulama kaydı.

Ağırlıklar doğrulama sonuçları açılmadan sabitlendi. Karşılaştırmalar aynı kaynak, seviye ve %87,5 örtüşme koşullarında yapıldı.

| Ölçüm | V1 | Önceki V2 | Yeni aday |
|---|---:|---:|---:|
| Vokal SDR (dB, yüksek iyi) | 11.417936 | 11.506172 | 11.949661 |
| Vokal SI-SDR (dB, yüksek iyi) | 10.989005 | 11.100407 | 11.600842 |
| Vokal eksik içerik göstergesi (düşük iyi) | 0.068425 | 0.066681 | 0.057697 |
| Vokal fazla içerik göstergesi (düşük iyi) | 0.005042 | 0.004871 | 0.004616 |
| Enstrümantal SDR (dB, yüksek iyi) | 18.227345 | 18.315581 | 18.759070 |
| Enstrümantal SI-SDR (dB, yüksek iyi) | 18.119079 | 18.207420 | 18.653884 |
| Enstrümantal eksik içerik göstergesi (düşük iyi) | 0.008487 | 0.008480 | 0.008085 |
| Enstrümantal fazla içerik göstergesi (düşük iyi) | 0.009020 | 0.008116 | 0.005283 |

| Karşılaştırma | Ortalama SDR farkı | %95 eşleştirilmiş bootstrap aralığı | İyileşen kayıt |
|---|---:|---:|---:|
| V1 | +0.531724 dB | [+0.285546, +0.886163] dB | 10/10 |
| Önceki V2 | +0.443489 dB | [+0.244026, +0.726839] dB | 10/10 |

SDR doğrudan örnek hata oranıdır; MVSEP veya BSSEval puanlarıyla aynı ölçüm değildir. Spektral göstergeler gerçek sızıntı yüzdeleri değildir.

Kabul için iki sürüme karşı pozitif SDR kazancı ve pozitif güven aralığı alt sınırı; iki kanalın ortalama SI-SDR ve dört içerik göstergesinin tamamında kötüleşmeme aranır. 0,2 dB ayrıca hedef olarak kaydedilir.

Bunlar kısa referans kayıtlarının ortalamalarıdır. Model eğitim verileriyle örtüşme bilinmiyor. Türkçe tam şarkılarda gerçek stüdyo kanalları olmadığı için kayıp veya sızıntı oranı ölçülemez. Her şarkıda üstünlük ve sıfır kayıp garantisi verilmez.

[Önceki başarısız denemeler dahil deney geçmişi](atlas-studio-v2-refinement-attempts.md). Checkpoint kimlikleri, ağırlıklar, tek tek kayıt sonuçları ve çalışma koşulları [JSON raporunda](atlas-studio-v2-refinement.json).

Üç Türkçe tam şarkı: 494.121 saniye. Gerçek üretim birleştiricisiyle süre/kanal boyutları korundu; çıktı toplamının kaynakla en büyük mutlak örnek farkı 5.96e-08. Bu kontroller seslerin doğru kanala atanmasını kanıtlamaz.

Canlı API isteği: 6 gerçek model, 132300 stereo örnek, 44100 Hz. İki WAV oluşturuldu; kaynak toplamı farkı 3.73e-08. Bu bir çalışma testi, ayrı kalite benchmarkı değildir.
