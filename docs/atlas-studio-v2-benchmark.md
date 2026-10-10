# Atlas Studio V1 / V2: karşılaştırmalı referans ön testi

10 Ekim 2026. Ayarlanmış V2, ağırlık seçiminde kullanılmayan **8 kısa kaydın
8'inde** V1'den daha düşük referans hatası verdi. Kazanç küçüktür:
ortalama **+0,0447 dB**. Bu sonuç bütün şarkılarda üstünlük veya sıfır kayıp değildir.

## Deney

- [SigSep'in resmi MUSDB 7 saniyelik örnek arşivi](https://github.com/sigsep/sigsep-mus-db/releases/tag/v0.4.0)
  kullanıldı. Dosya adlarının sabit SHA-256 sıralamasıyla 8 geliştirme (train),
  8 değerlendirme (test) kaydı seçildi; sonuçlara göre kayıt seçilmedi.
- Gerçek vokal referansı ile bas + davul + diğer enstrümanların toplamı kullanıldı.
  Kaynak bunların toplamından oluşturuldu; ayrı AAC miksin kodlama farkı dışlandı.
- Beş gerçek model × 16 kayıt = **80 ayrıştırma**. Aynı 44,1 kHz stereo kaynak,
  16 saniyeye doldurma, seviye payı, doğal model penceresi, batch 1 ve örtüşme
  katsayısı 8; float WAV çıktıları. Gate, EQ veya kanal başına normalizasyon yok.
- Beş modelden oluşan havuzun dört modellik beş alt kümesi geliştirme verisinde
  denendi. Negatif olmayan ve toplamı 1 olan ağırlıklar SLSQP ile ayarlandı.
  Hedef, iki kanalın normalize örnek hatası ile STFT büyüklük hatasının toplamıdır.
- Geliştirme verisinde iki kanalın eksik/fazla spektral içerik göstergelerinin
  V1'i aşmaması kısıtı uygulandı. Optimizasyon sabit seyrek STFT ızgarasını,
  nihai değerlendirme tam ızgarayı kullandı. Yakınsamayan çözümler seçilmedi.
- Model ve ağırlık seçimi bittikten sonra karışım sabitlendi; değerlendirme
  kayıtları ağırlık seçiminde okunmadı. Test sonucu görüldükten sonra ağırlıklar değiştirilmedi.

## Ayrı değerlendirme kayıtlarının ortalaması

SDR burada referans enerjisi / doğrudan hata enerjisinin dB oranıdır. BSS Eval
v4 filtreli SDR veya MVSEP tablosuyla doğrudan karşılaştırılmamalıdır.

| Karışım | Vokal SDR (dB) | Enstrümantal SDR (dB) | Vokal SI-SDR | Enstrümantal SI-SDR |
|---|---:|---:|---:|---:|
| V1 | 12,6973 | 18,2750 | 12,4104 | 18,2014 |
| İlk V2 | 12,6177 | 18,1953 | 12,3536 | 18,1220 |
| Ayarlanmış V2 | **12,7420** | **18,3196** | **12,4616** | **18,2469** |

Her iki kanalın ortalama yardımcı göstergeleri de iyileşti:

| Normalize STFT büyüklük hatası; düşük daha iyi | V1 | Ayarlanmış V2 |
|---|---:|---:|
| Vokal eksik büyüklük | 0,0369247 | 0,0367300 |
| Vokal fazla büyüklük | 0,00501749 | 0,00488580 |
| Enstrümantal eksik büyüklük | 0,00606070 | 0,00604022 |
| Enstrümantal fazla büyüklük | 0,00261715 | 0,00254821 |

Bu ölçüler eksik/fazla ses için yardımcı göstergelerdir; gerçek sızıntı yüzdesi,
kelime kaybı veya MVSEP Fullness/Bleedless puanları değildir. Ayrı kayıtların
her birinde bütün yardımcı göstergelerin iyileştiği iddia edilmiyor.

Eşleştirilmiş şarkı bootstrap'ında (sabit tohum, 10.000 tekrar) ortalama SDR
farkının %95 aralığı **+0,0277 ile +0,0632 dB**. Küçük örneklem belirsizliğini
özetler; yeni türlerde üstünlük garantisi oluşturmaz. Tamamlayıcı iki kanalda
aynı örnek hatası oluştuğu için SDR farkı iki kanalda aynı; bunlar bağımsız iki
üstünlük kanıtı sayılmamalıdır.

## Uygulanan karışım

| Model | Ağırlık |
|---|---:|
| BS-Roformer-Viperx-1297 | %47,369644 |
| BS Roformer Leap Vocals by pcunwa | %6,874970 |
| MelBand Roformer Kim FT2 Bleedless | %19,796380 |
| MelBand Roformer Kim Inst V2; kaynak farkından vokal tahmini | %25,959006 |

Becruily seçilen karışıma girmedi. İlk V2'deki %55 Leap ağırlığı desteklenmedi.
V1'in kendi ağırlıkları korunuyor. V2'yi seçmek için preseti yeniden uygulayın.

Uygulamanın gerçek birleştirme fonksiyonu 16 kaydın tamamında sabitlenmiş
benchmark karışımıyla eşleşti. İki kanal toplamının kaynaktan maksimum mutlak
örnek farkı, dışa aktarımdan önce **5,5511 × 10⁻¹⁷** idi. Bu toplam kontrolüdür,
doğru kanal atamasının ayrıca kanıtı değildir.

## Sınırlar ve yeniden çalıştırma

7 saniyelik AAC örnekleri kullanıldı; tam şarkı, uzun solo, Türkçe/arabesk ve
eski kayıtlar için geniş doğrulama yapılmadı. Modellerin eğitiminde bu kayıtların
bulunup bulunmadığı bilinmiyor: değerlendirme seti yalnızca karışım ağırlıklarının
seçiminden ayrıdır. Kör dinleme yapılmadı. İncelenen beş model ve karışım yöntemi
arasında ön test yapıldı; bütün mevcut modeller arasında küresel optimum iddiası yok.

Ham kayıt bazlı sonuçlar, seçilmeyen çözümler, sürümler ve dosya SHA-256 değerleri:
[benchmark JSON](atlas-studio-v2-benchmark.json). Referans sesler ve model ağırlıkları
Git'e eklenmez. Verilerin kullanım koşulları için [SigSep veri sayfası](https://sigsep.github.io/datasets/musdb.html).

Depo kökünde, sırayla:

```powershell
.\env\python.exe tools/atlas_benchmark.py prepare
.\env\python.exe tools/atlas_benchmark.py infer
.\env\python.exe tools/atlas_benchmark.py fit
.\env\python.exe tools/atlas_benchmark.py evaluate
.\env\python.exe tools/atlas_benchmark.py export
```

`fit` üretim presetini otomatik değiştirmez. Deneyi yeniden yapmak için
orijinal beş aday modelin kimlikleri preset değişikliklerinden bağımsız tutulur.
