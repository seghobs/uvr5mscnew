# Atlas V2: genişletilmiş deney

Bu deney sürerken üretimdeki V2, önceki referans ön testinde seçilmiş sabit
ağırlıkları kullanır. Yeni adayın sonuçları ölçülmeden preset değiştirilmez.

## Önceden belirlenen yöntem

Resmî MUSDB 7 saniyelik örnek arşivinde sabit dosya sıralamasından 16 train
kaydı geliştirme için, önceki değerlendirmeye girmeyen test[8:16] kayıtları
ayrı değerlendirme için seçilir. Önceki test[0:8] bu deneye dahil edilmez.
Model eğitim verileriyle örtüşme bilinmiyor; bu, tamamen bağımsız bir model
genelleme sertifikası değildir.

Viper 1297, Leap, FT2 Bleedless, becruily, Inst V2, Revive 2 ve Revive 3e
aynı kaynak/seviye/örtüşme koşullarında denenir. V1'in üç uzmanı ile bir
ek uzmandan oluşan dört modellik karışım, 10 frekans noktasında negatif
olmayan ve toplamı 1 olan ağırlıklarla ayarlanır. Noktalar arasında doğrusal
geçiş ve ağırlık değişimlerine yumuşatma cezası kullanılır. Model seçimi,
yumuşatma ve V1'e geri karıştırma oranı yalnızca geliştirme kayıtlarında
belirlenir. Gate, kelime susturma ve ara müziği değiştirme kullanılmaz.

Yeni adayı üretime geçirmek için ayrı değerlendirme kayıtlarında:

- Ortalama doğrudan referans SDR kazancı V1'e göre en az 0,2 dB olmalı.
- Şarkı bazında eşleştirilmiş bootstrap %95 aralığının alt sınırı sıfırdan büyük olmalı.
- Her iki kanalın ortalama SI-SDR değeri ve dört spektral eksik/fazla içerik
  göstergesi V1'e göre kötüleşmemeli.

Bunlar mühendislik kabul ölçütleridir; bütün şarkılarda işitilebilir üstünlük
veya sıfır kayıp garantisi değildir. Başarısız değerlendirmeden sonra aynı
test kayıtlarına bakarak ağırlıklar yeniden seçilmez.

## Türkçe tam şarkılar

Kullanıcının `ytdl` klasöründeki Bilal Sonses – Nefret, Ezhel – Başa Bela ve
Müslüm Gürses – Gözleri Fettan Güzel tam süreleriyle işlenir. V1, mevcut V2
ve yeni aday için karşılaştırma WAV'ları üretilir. Süre, sonlu örnekler ve
iki kanalın kaynak toplamını koruması kontrol edilir.

Bu klasör orijinal miksleri içerir. Gerçek stüdyo kanalları olmadığı için
Türkçe tam şarkılarda SDR, gerçek sızıntı oranı veya kayıp miktarı raporlanamaz.
İki kanalın toplamının kaynağı vermesi, seslerin doğru kanala dağıtıldığını
kanıtlamaz. Önceki yapay zekâ çıktıları gerçek referans olarak kullanılmaz.

Tekrar çalıştırma: Önce `tools/atlas_benchmark.py prepare` ile resmî örnek
arşivi hazırlanır. `tools/atlas_extended.py` sırasıyla `infer`, `fit`,
`evaluate`, `full-infer`, `full-export` aşamalarını sunar. Deney çıktıları
`cache/atlas_extended` altında saklanır. `export-report` ölçüm ve model
dosyası kimliklerini `docs/atlas-studio-v2-expanded.json` içine aktarır.

## Ölçülen referans sonucu

Yedi model × 24 kayıt = **168 gerçek model çıktısı** karşılaştırıldı; bunların
40'ı aynı koşullarda önceki deneyde üretilmişti, 128'i yeni üretildi. Ek
Revive modelleri denendi fakat geliştirme verisinde seçilen dört uzman
Viper, Leap, FT2 Bleedless ve Inst V2 oldu. Basitçe daha fazla model eklemek
bu deneyde daha iyi bir karışım sağlamadı.

Yeni aday ayrı değerlendirmede 8 kaydın 7'sinde V1'den daha düşük hata verdi.
Ortalama SDR kazancı **+0,2836 dB**, eşleştirilmiş bootstrap %95 aralığı
**[+0,1009; +0,5150] dB**. Bir kayıtta **−0,1176 dB** gerileme var.
SDR burada doğrudan örnek hatasıdır; MVSEP/BSS Eval SDR ile aynı değildir.

| Ayrı değerlendirme ortalaması | V1 | Mevcut V2 | Yeni frekans adayı |
|---|---:|---:|---:|
| Vokal SDR, dB | 12,2643 | 12,3328 | **12,5479** |
| Enstrümantal SDR, dB | 15,5492 | 15,6178 | **15,8328** |
| Vokal SI-SDR, dB | 11,8458 | 11,9240 | **12,0842** |
| Enstrümantal SI-SDR, dB | 15,4422 | 15,5125 | **15,7323** |
| Vokal eksik spektral içerik | **0,1484081** | 0,1489667 | 0,1487644 |
| Vokal fazla spektral içerik | 0,0055609 | 0,0053087 | **0,0051750** |
| Enstrümantal eksik spektral içerik | 0,0098350 | **0,0096868** | 0,0097304 |
| Enstrümantal fazla spektral içerik | **0,0239704** | 0,0240336 | 0,0239719 |

Yeni aday ortalama referans hatasını daha fazla azaltıyor; ancak vokal
eksik içerik ve enstrümantal fazla içerik göstergeleri V1'e göre az da olsa
kötüleşiyor. Bu yüzden **önceden belirlenen üretim kabul ölçütünü geçmedi**.
Üretimdeki preset değiştirilmedi. Adayın daha düşük örnek hatası, iki tarafta
da kayıpsızlık veya her şarkıda üstünlük olarak sunulamaz. Bu yardımcı
göstergeler gerçek sızıntı yüzdeleri değildir.

Önceki +0,0447 dB ön test başka sekiz değerlendirme kaydını kullanmıştı;
bu sayıyla yeni sonucu bölerek kalite artışı katsayısı üretmek doğru olmaz.
Buradaki aynı kayıtlarda mevcut V2'nin kazancı +0,0685 dB'dir.

## Tam şarkı işlemlerinin tamamlanması

Üç Türkçe kayıt toplam **494,121 saniye** boyunca dört uzmanla işlendi:
**12 tam şarkı/model ayrıştırması**, üç karışım × üç şarkı × iki kanal =
**18 tam uzunlukta WAV**. Bütün dosyalar yeniden okunarak süre, stereo yapı,
sonlu örnekler ve kaynak toplamı doğrulandı. En yüksek toplam farkı
**8,94 × 10⁻⁸**; bu float WAV hassasiyeti düzeyindedir. Seslere ayrı ayrı
normalizasyon veya limiter uygulanmadı.

Karşılaştırma bağlantıları `cache/atlas_extended/KARSILASTIRMA.md` içinde.
Ayrıntılı ölçüm ve kaynak/model dosyası SHA-256 bilgileri bu belgenin
yanındaki `atlas-studio-v2-expanded.json` dosyasında. 49 ilgili test geçti.

Tam kayıt işlemlerinde teknik bir kesilme veya bozuk çıktı bulunmadı.
Bu, Türkçe şarkılarda vokal/enstrüman kaybının azaltıldığının ölçümü değildir;
o değerlendirme için aynı kayıtların gerçek stüdyo kanalları gerekir.
