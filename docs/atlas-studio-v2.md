# Atlas Studio V2 — araştırma ve sınırlar

10 Ekim 2026. Güncel preset altı modelin çıktısını frekanslara göre birleştirir.
Her şarkıda sıfır sızıntı veya Atlas V1'e üstünlük garantisi yoktur.

## İncelenen model aileleri

Kaynak: https://mvsep.com/en/algorithms

| Aile | Bulgular ve karar |
|---|---|
| BS Roformer 124 bant, 2026.07 | Yayıncı tablosunda %87 örtüşmeyle vokal SDR 12.39, enstrüman SDR 18.70. Yerel model adı yanlış Leap adresine bağlanmış; bu ağırlıklar doğrulanamadığı için V2'de kullanılmadı. |
| BS Roformer Leap | Yayıncının gerçek dosyaları ve yapılandırması doğrulandı: 62 bant, dim 256. Ön testte Viper'ı destekleyen düşük ağırlıklı uzman; 124 bant puanları bu modele atfedilmez. |
| MelBand Roformer | Vokal ve enstrüman uzmanları; fullness sürümlerinde daha fazla sızıntı olabilir. Destek modelleri. |
| BS PolarFormer | 124 bant sürümü tabloda 12.02 / 18.33; yerel çalışma zincirinde doğrulanmış destek yok. Eklenmedi. |
| SCNet XL IHF | 11.11 / 17.41; farklı hatalar üretebilir, fakat mevcut yerel Roformer yürütücüsüyle uyumlu değil. |
| MDX23C | Tam bant modeller; tabloda en iyi listelenen sürüm 10.36 / 16.66. V2'ye rastgele eklemek kalite kanıtı olmaz. |
| MDX-Net / VR | Daha eski aileler; belirli kayıtlarda yararlı olabilir. Ana iki kanal presetinde tercih edilmedi. |
| Demucs | Bas, davul ve çoklu kanal için yararlı; burada hedef yalnızca vokal/enstrüman. |
| Karaoke, de-reverb, denoise, enstrüman uzmanları | Arka vokal, yankı veya müzikal bileşen silebilir. Bu hedef için uygulanmıyor. |
| MVSep Ensemble / All-In | Yayıncının özel model ve ağırlıklarına sahip değiliz. Aynı sonucu elde ettiğimizi iddia etmiyoruz. |

Tablo puanları yayıncının veri kümesine aittir. Model adındaki 1297 ile buradaki
SDR değerleri farklı değerlendirmelerdir; doğrudan karşılaştırılamaz.

## Güncel preset

Viper 1297, Leap, MelBand FT2 Bleedless, MelBand Inst V2 ve
[Resurrection vokal/enstrümantal uzmanları](https://huggingface.co/pcunwa/BS-Roformer-Resurrection/tree/8fc1a62f765e3e738db8394d7e87e379acc4c675)
kullanılır. Yayıncı checkpoint'leri sabit bir sürüme bağlandı; model ağırlıkları
değiştirilmedi. İki yeni modelin kısa girdi penceresi ve tek hedef kanal
etiketleri, kullanılan yerel kütüphane için düzeltildi.

Karışım, daha önce incelenmiş 56 geliştirme kaydında 10 frekans noktasına göre
ayarlandı. Ağırlıklar negatif değildir ve her frekansta toplamı 1'dir.
Model çıktıları aynı seviye/zaman tabanındadır; enstrüman kaynak − vokal olarak
üretilir. Gate, kelime susturma ve orijinal ara müzikle değiştirme kullanılmaz.
%87,5 örtüşme, doğal model penceresi, batch 1 ve float WAV korunur.
Altı model sırayla çalışır; önceki dört modelli V2'ye göre daha uzun sürer.

Sabitlenen karışım önce ayrı 8 kayıtta, sonra önceden ayrılmış son 10 kayıtta
değerlendirildi. Son 10 kaydın tamamında SDR yükseldi: ortalama +0,4435 dB
önceki V2'ye, +0,5317 dB V1'e göre. Önceki V2 farkının %95 eşleştirilmiş
bootstrap aralığı [+0,2440, +0,7268] dB. Her iki kanalın ortalama SI-SDR ve
dört spektral eksik/fazla içerik göstergesi de iyileşti.

Önceki V2'ye göre son grupta vokal eksik içerik göstergesi %13,47,
enstrümantal eksik içerik göstergesi %4,66 azaldı. Bunlar gerçek sızıntı
veya kayıp yüzdeleri değildir. Ayrıntılar ve sınırlar:
[son doğrulama](atlas-studio-v2-refinement.md),
[başarısız adaylar dahil deney geçmişi](atlas-studio-v2-refinement-attempts.md).

Türkçe tam şarkıların orijinal miksleri gerçek stüdyo kanalları değildir.
Bu dosyalarda süre ve kaynak toplamı kontrolleri yapılabilir; gerçek kanal
kaybı ölçülemez. Bu nedenle bütün şarkılarda üstünlük veya sıfır kayıp
garantisi verilmez.

## Önceki V2 ön testi (tarihsel)

- Viper 1297: %47,3696; BS Roformer Leap: %6,8750;
  MelBand FT2 Bleedless: %19,7964; Inst V2'nin kaynak farkı: %25,9590.
- Ağırlıklar 8 gerçek referans kaydında ayarlandı, ayrı 8 kısa kayıtta değerlendirildi.
  Becruily seçilen karışıma girmedi. Ayrıntılar: [karşılaştırmalı test raporu](atlas-studio-v2-benchmark.md).
- %87,5 örtüşme, doğal model penceresi, batch 1, dört model sırayla çalışır.
- Vokal tahmini ağırlıklı ortalamadır; enstrüman = çözümlenmiş kaynak − vokal.
  Böylece toplam korunur, fakat yanlış kanala atanan ses geri dağıtılamaz.
- Varsayılan float WAV; gate, bağımsız normalizasyon ve gürültü temizleme yok.
  FLAC taşma durumunda iki kanalı aynı miktarda azaltır.
- Kaynak 44.1 kHz stereo çözümlenir; korunma bu çözümlenmiş kaynağa göredir.
  MP3 kaynağın geçmiş sıkıştırma kaybı geri getirilemez. Float dışa aktarımda yuvarlama vardır.

## Doğrulama

İlk aday karışımın canlı çalışma testi: yerel MP3 kaydının 40–43 saniyeleri, 132300 stereo örnek.
Dört gerçek model çalıştı ve float WAV çifti üretildi. Süre/kanal boyutları
korundu. Kaynak ile iki çıktı toplamı arasındaki maksimum mutlak örnek farkı
2.9802322387695312e-08 idi. Bu bir uyumluluk/toplam testi, kalite benchmarkı değildir.

Sentetik birleştirme testleri toplam, ağırlıklar, geçersiz çıktı reddi ve V1/V2
model karışıklığını kontrol eder. Bu testler ses ayrıştırma kalitesini ölçmez.
Üstünlük için gerçek vokal/enstrüman referansları, aynı kayıtta V1/V2 SDR ve
dinleme karşılaştırması gerekir. Sıfır hatalı ayrıştırma raporlanmıyor.

Leap indiricisi eski yanlış adres yerine yayıncının gerçek CKPT/YAML çiftini
kullanır. Yapılandırmalar ayrı klasörlerde tutulur. Stock audio-separator için
eşdeğer varsayılan eğitim seçenekleri kaldırılır; pencere hop uzunluğu gerçek
STFT hop uzunluğuyla eşleştirilir. Model ağırlıkları değiştirilmez.

## Genişletilmiş araştırma: üstünlük iddiasının kanıt düzeyi

Leap yayıncısı, standart checkpoint'in MVSEP #10146 olduğunu doğruluyor.
Testi yapan kişi yalnızca overlap değerini 4 yaptığını belirtiyor. Dolayısıyla
bu puanları yerel %87,5 örtüşmeli dört model karışımının puanı diye sunamayız.
İlgili testte vokal SDR 11.7222, enstrüman SDR 17.7794; vokal
Bleedless 38.9019 ve Fullness 17.0702. Bunlar sıfır sızıntı kanıtı değildir.

- [Checkpoint kimliği ve test ayarı](https://huggingface.co/pcunwa/BS-Roformer-Leap/discussions/2)
- [Leap test sonucu](https://mirror.mvsep.com/quality_checker/entry/10146)

MVSEP'in tanımına göre Fullness eksik içerikle, Bleedless eklenen istenmeyen
içerikle ilgilidir. İkisi de 0–100 ölçeğinde puanlardır; doğruluk yüzdesi değildir.
Yayıncı, eğitim sırasında bu hedeflerin çoğunlukla birbirine karşı çalıştığını
belirtiyor. Aynı değerlendirme platformundaki somut örnek:

| MVSEP karışımı | Vokal SDR | Vokal Fullness | Vokal Bleedless | Enstrüman SDR |
|---|---:|---:|---:|---:|
| Standart, #8479 | 11.9307 | 17.7342 | 36.2970 | 18.2381 |
| Yüksek vokal dolgunluğu, #8482 | 11.6976 | 20.4628 | 32.7769 | 18.0061 |

Daha yüksek dolgunluk burada daha düşük sızıntı önleme ve SDR ile birlikte
geliyor. Bu örnek Atlas V1/V2 karşılaştırması değildir; tek bir kalite hedefini
artırmanın bütün hedeflerde üstünlük sağlamadığını gösterir.

- [Ölçüt tanımları](https://mirror.mvsep.com/faq/4)
- [Standart karışım](https://mvsep.com/quality_checker/entry/8479)
- [Dolgunluk karışımı](https://mvsep.com/quality_checker/entry/8482)

MSST'nin resmi ensemble dokümanı, düşük kaliteli bir modeli karışıma eklemenin
sonucu kötüleştirebildiğini açıklıyor. Ağırlıklı ortalama desteklenir, fakat dört
model iki veya üç modelden otomatik olarak üstün değildir. Mühendislik çıkarımı:
modeller aynı yerde hata yaptığında ortalama bu hatayı ortadan kaldırmaz.
İlk V2'nin %55/%15/%10/%20 ağırlıkları testte V1'den daha yüksek hata verdi;
yerlerine karşılaştırmalı ön testte seçilen Viper/Leap/FT2/Inst V2 karışımı geçti.

MDX Challenge makalesi MUSDB18'in Batı pop müziği ve sınırlı miks mühendisi
çeşitliliğine bağlı yanlılıklarını açıklıyor. Buradan çıkan değerlendirme kararı:
Türkçe, arabesk, eski mono/stereo kayıt ve canlı performanslar ayrıca sınanmalıdır.
Genel liderlik tablosu bu repertuvar için garanti oluşturmaz.

- [MSST ensemble dokümanı](https://github.com/ZFTurbo/Music-Source-Separation-Training/blob/main/docs/ensemble.md)
- [MDX Challenge araştırması](https://arxiv.org/abs/2108.13559)

## V1'e üstünlük için gereken kabul testi

Kısa referans kayıtlarıyla ilk ön test uygulandı. Aşağıdaki protokolün tam şarkı,
geniş repertuvar ve kör dinleme kısımları henüz tamamlanmadı.

1. Gerçek referans vokal/enstrüman kanalları bulunan, farklı türlerden kayıtlar
   kullanılır. İki sistem de aynı çözümlenmiş ses ve aynı seviye ile değerlendirilir.
2. Karışım ağırlıkları ayrı geliştirme kayıtlarında ayarlanır; nihai test kayıtları
   bu seçimde kullanılmaz. V1, Leap tek başına ve V2 karşılaştırılır.
3. Her iki kanal için SDR, SI-SDR, Fullness ve Bleedless raporlanır. Ortalama
   yanında şarkı başına kötüleşmeler ve en kötü örnekler gösterilir.
4. Sessiz vokal, nefes, arka vokal, yankı, yaylı/gitar ve solo bölümleri ayrıca
   incelenir; eşit ses seviyesinde isimleri gizlenmiş dinleme karşılaştırması yapılır.
5. İki kanalda da iyileşme gözlenmeden "V1'den üstün" etiketi kullanılmaz.
   İstatistiksel belirsizlik raporlanır; testte kazanmak tüm yeni şarkıları garanti etmez.

Referans kanalları olmayan bir şarkıda toplam sesin korunması ölçülebilir;
her sesin doğru kanala gittiği kesin olarak ölçülemez. V1'e otomatik geri dönüş
de ancak güvenilir kalite ölçümü varsa işe yarar. Başka bir modelin kararı,
model uzlaşması veya toplamın korunması tek başına bu garantiyi sağlayamaz.

Son karar: Ayarlanmış V2, ağırlık seçiminde kullanılmayan 8 kısa kaydın 8'inde
V1'den daha düşük hata verdi; ortalama fark +0,0447 dB ile küçüktür. Her iki
kanalın ortalama spektral eksik/fazla içerik göstergeleri de azaldı. Bu sonuç
tam şarkılara veya her repertuvara üstünlük garantisi değildir. Daha yüksek
overlap veya daha fazla model ekleyerek sıfır kayıp iddiası yapılmaz.

Kaynaklar:
- https://mvsep.com/en/algorithms
- https://github.com/ZFTurbo/Music-Source-Separation-Training/blob/main/docs/ensemble.md
- https://huggingface.co/pcunwa/BS-Roformer-Leap
- https://huggingface.co/pcunwa/BS-Roformer-Revive
- https://arxiv.org/abs/2310.01809
