# Karaoke kelime zamanlaması analizi

Kelime dolgusunun sürekli elle düzeltilmesi, birden fazla aşamanın aynı zaman bilgisini değiştirmesinden kaynaklanıyor. Mevcut kodda otomatik söz çıkarma, metin düzenleme, otomatik kayıt, önizleme ve video oluşturma aynı kelime zamanlarını korumuyor. Daha iyi bir söz tanıma modeli tek başına bu hataları gideremez.

Bu değerlendirme mevcut kaynak koduna, SQLite kayıtlarının salt okunur incelemesine, üretilmiş ASS altyazılarının yapısına ve kaynak kodundan alınan fonksiyonlarla yapılan izole deneylere dayanır. Belirli bir şarkının doğru zamanları dinlenerek etiketlenmedi; aşağıdaki ölçümler model doğruluk oranı değildir. Yeni GPU çıkarımı veya uçtan uca tarayıcı testi yapılmadı. Uygulama kodu ve mevcut kayıtlar değiştirilmedi.

## 1. Elle ayarlanan zamanlar video öncesinde değiştiriliyor

`frontend/src/components/KaraokeStudioModal.tsx:101` içindeki `fitWordsToSegmentRange`, ilk kelimenin başlangıcı ile son kelimenin bitişini satırın başlangıç ve bitişine ölçekliyor. Bu fonksiyon yalnızca açıkça bir ölçekleme istendiğinde kullanılmıyor: metin değişikliklerinde ve `handleGenerateVideo` içinde her satır için tekrar çağrılıyor (`:1244`).

Örneğin satır 10–13 saniye olsun. Gerçek kelime aralıkları 10,40–11,00 ve 11,50–12,50 iken fonksiyonun gerçek kodunu çalıştırınca sonuç 10,00–10,86 ve 11,57–13,00 oluyor. Birinci kelime 400 ms erken başlıyor; ikinci kelime 500 ms fazla sürüyor. Satırın görünme aralığı ile şarkıcının söylediği kelime aralıklarının farklı olabilmesi gerekiyor.

Elle ilk kelimeyi ileri almak da bunu tetikleyebilir: `handleWordTimeChange`, satır başlangıcını yalnızca küçültüyor ve bitişini yalnızca büyütüyor (`:664`). Dolayısıyla satırda bir baş boşluğu kalabiliyor; video öncesi ölçekleme bu boşluğu tekrar ortadan kaldırıyor.

Metindeki kelime sayısı değişirse fonksiyon mevcut zamanları bırakıp ünlü/hece ağırlıklarıyla yeniden dağıtıyor. Noktalama veya metin temizliği kelime sayısını etkilediğinde de aynı risk var. Ölçülmüş zamanlarla tahmini zamanlar veri modelinde ayrılmıyor.

**Gerekli değişiklik:** Satırın ekranda görünme aralığını kelimelerin söylenme aralığından ayırmak; video oluştururken doğrulanmış kelime zamanlarını aynen korumak; ölçeklemeyi ayrı ve açık bir düzenleme işlemi yapmak.

## 2. Video oluşturucu zamanları ikinci kez yeniden dağıtıyor

`api_modern.py:2125–2169` kelimelerin mutlak başlangıçlarını doğrudan ASS zaman çizelgesine çevirmek yerine süreleri ve araları toplayıp satır süresine oranlıyor. Bu sırada:

- 80 ms altındaki kelime süreleri en az 80 ms yapılıyor.
- 80 ms altındaki kelime araları sıfırlanıyor.
- 600 ms üzerindeki aralar hesaplamaya en fazla 600 ms olarak giriyor.
- Elde edilen süreler satırın toplam süresine yeniden ölçekleniyor.
- İlk kelimeden önceki bekleme ayrı bir zaman olayı olarak yazılmıyor.

Kaynak kodundan çıkarılan gerçek ASS üretim bloğuyla iki deney yapıldı:

| Durum | Girilen kelime aralıkları | ASS içindeki dolgu aralıkları |
|---|---|---|
| Kelimeler arasında 1,20 s es | 10,00–11,00 / 12,20–13,20 | 10,00–11,23 / 11,97–13,20 |
| Kelimeler arasında 50 ms es | 10,00–10,50 / 10,55–11,05 | 10,00–10,52 / 10,52–11,05 |

İlk örnekte ikinci kelime 230 ms erken dolmaya başlıyor. Bu fark, doğru zamanlar verilse bile oluşuyor. ASS `\kf` efekti kendisine verilen süre boyunca soldan sağa renk doldurur; ses sinyalini analiz etmez. Bu nedenle yanlış süreyi FFmpeg ayarıyla düzeltmek mümkün değildir. [Aegisub ASS tanımı](https://aegisub.org/docs/latest/ass_tags/#karaoke-effect)

**Gerekli değişiklik:** Mutlak kelime sınırlarından, baştaki ve aradaki beklemeleri koruyan tek bir zaman çizelgesi üretmek. Santisaniyeye yuvarlamayı bir kez yapmak; geçersiz aralıkları sessizce yaymak yerine açıkça işaretlemek. Çok kısa aralıkların toplam süreyi değiştirmediğini ve video kareleriyle uyumunu test etmek.

## 3. Otomatik kayıt önceki düzenlemeyi geri yazabiliyor

`triggerAutoSave` yeni veriyi 350 ms sonra kaydetmek üzere zamanlayıcı kuruyor (`KaraokeStudioModal.tsx:551`). Ancak hemen aşağıdaki efektin temizleme fonksiyonu `segments` değiştiğinde de çalışıyor; sadece pencere kapanırken çalışmıyor (`:562–574`). Bu fonksiyon yeni zamanlayıcıyı iptal edip önceki render'ın `segments` değerini kaydediyor.

Gerçek `triggerAutoSave` ve efekt kodunun izole yürütülmesinde şu sıra doğrulandı:

1. Eski kelime başlangıcı 10,00 s.
2. Yeni düzenleme 10,40 s ve gecikmeli kayıt planlanıyor.
3. Önceki efektin temizliği çalışıyor.
4. Yeni kayıt iptal ediliyor; API'ye 10,00 s gidiyor.

Hızlı/immediate kayıt yollarında eski ve yeni istekler de çakışabilir. Kesin sonucun hangi isteğin son tamamlandığına bağlı olduğu yollar vardır. Kullanıcının ekranda gördüğü yeni değer ile yeniden açıldığında yüklenen değer farklı olabilir.

**Gerekli değişiklik:** En son veriyi ayrı bir referansta tutmak; kayıtları sıraya almak veya sürüm numarasıyla korumak; kapanışta yalnızca en güncel sürümü göndermek. Metin düzenleme, kelime düzenleme, hızlı ardışık değişiklik ve pencere kapatma senaryolarını test etmek.

## 4. “Sözleri yapıştır ve hizala” gerçek metin-ses hizalaması yapmıyor

Arayüz yapıştırılan metni normal transkripsiyon isteğine gönderiyor (`KaraokeStudioModal.tsx:2609`). Sunucu yalnızca ilk 350 karakteri `initial_prompt` olarak kullanıyor (`api_modern.py:1727`). Tam metni sesle eşleştiren, metindeki her kelime için başlangıç ve bitiş arayan ayrı bir işlem bulunmuyor.

Faster-Whisper belgelerinde `initial_prompt` ilk pencereye verilen metin ipucu olarak açıklanıyor. `word_timestamps` ise tanınan metin için dikkat örüntüleri ve dinamik zaman bükme yöntemiyle zaman çıkarıyor. Bunlar, sağlanan bütün şarkı sözlerinin zorunlu olarak hizalanması anlamına gelmiyor. [Faster-Whisper kaynak açıklaması](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py)

Ayrıca `fetchInitialLyrics` hatayı kendi içinde yakaladığı için dıştaki yapıştırma akışı bazı başarısızlıklardan sonra da “hizalandı” mesajı gösterebilir.

**Gerekli değişiklik:** Doğru sözler biliniyorsa tam metni ve vokal sesini alan gerçek bir forced alignment aşaması eklemek. Dil uyumlu hizalayıcı kullanılmalı; tanınmayan veya şüpheli kelimeler kullanıcıya gösterilmeli. WhisperX bu yaklaşımın bir örneğidir; dil özelinde model gerektirir ve örtüşen konuşmada sınırlamaları vardır. Türkçe şarkı söylemede performansı bu projenin örnekleriyle ayrıca ölçülmelidir; kusursuz otomasyon garantisi değildir. [WhisperX](https://github.com/m-bain/whisperX)

## 5. İlk sözlerin bir kısmı uygulama filtresiyle silinebiliyor

`api_modern.py:1770` ilk 15 saniyedeki bir kelimeyi, süresi 250 ms'den kısaysa **veya** güveni 0,35 altındaysa tamamen atıyor. Güveni yüksek fakat hızlı söylenen gerçek bir kelime de bu koşula takılır. Ayrıca “müzik”, “teşekkürler” gibi bazı ifadeleri içeren kelimeler bağlama bakılmadan eleniyor.

Faster-Whisper başarısız olursa kullanılan diğer Whisper yolunda `word_timestamps=True` verilmediği gibi dönen kayıtlara `words: []` yazılıyor (`:1843–1862`). Arayüz daha sonra hece ağırlıklarıyla tahmini kelime süreleri üretir. Böylece gerçekte ölçülmemiş bir kelime dolgusu otomatik sonuç gibi görünebilir.

**Gerekli değişiklik:** Şüpheli kelimeleri silmek yerine işaretlemek; kaynağı ve güven bilgisini saklamak; kelime zamanlaması bulunmayan sonuçları tahmin olarak açıkça ayırmak. VAD ve filtre eşiklerinin şarkıya etkisini ayrı deneylerle değerlendirmek.

## 6. Düzenleme önizlemesi video dolgusu ile aynı değil

Arayüzde ana satır dolgusu `(currentTime - seg.start) / satır_süresi` ile hesaplanıyor (`KaraokeStudioModal.tsx:1929`). Kelime süreleri bu barı etkilemiyor. Açılmış kelime kartları ise yalnızca aktif/pasif renk değiştiriyor (`:2220`). Bu nedenle satır çubuğuna bakarak MP4 içindeki gerçek kelime dolgusunu doğrulamak mümkün değil.

Oynatma saati yalnızca `timeupdate` olayından güncelleniyor (`:307`, `:355`). Bu olay sabit kare hızında değildir; MDN yaklaşık 4–66 Hz aralığı belirtir. Kısa kelimelerde işaret atlaması ve basamaklı ilerleme görülebilir. [MDN timeupdate](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/timeupdate_event)

Daha önemlisi, ses yükleme efekti `segments` bağımlılığı içeriyor (`:367`). Her düzenleme `audio.src` atamasını ve `audio.load()` çağrısını yeniden çalıştırıyor (`:297–298`). Çalarken kelime düzenlemek veya Space ile canlı senkron yapmak, ölçüm sırasında sesi yeniden yükleyebilir. Bu kod yolu doğrulandı; belirli tarayıcıda kesintinin süresi ölçülmedi.

**Gerekli değişiklik:** Ses kaynağını yalnızca dosya değiştiğinde yüklemek; güncel satırları oynatma dinleyicisine referansla vermek; animasyonu gerçek ses saati üzerinden kare bazında çizmek. Önizleme ve ASS aynı kelime zaman çizelgesini kullanmalı.

## 7. JSON yedekleme kelime zamanlarını kaybediyor

JSON dışa aktarımı yalnızca `start`, `end`, `text` alanlarını yazıyor (`KaraokeStudioModal.tsx:893`). İçe aktarma da yalnızca bu alanları okuyor (`:966`). Elle ayarlanmış `words` bilgisi bir dışa/içe aktarma turunda kayboluyor. Sonrasında yine tahmini dağılım devreye giriyor.

**Gerekli değişiklik:** Sürümlü proje formatında kelimeler, zamanlar, ses kimliği ve zamanlama kaynağı eksiksiz korunmalı. Dışa aktar → içe aktar eşitlik testiyle doğrulanmalı. Mevcut LRC/SRT akışları yalnızca satır verisini taşıyor.

## Kayıtlı verideki durum

`assets/favorites.db` içinde 100 kayıt bulundu. Aynı zamanlama JSON'unu taşıyan kayıtlar tekilleştirildiğinde 28 farklı veri kümesi, 802 satır ve 3.858 kelime var. Bunlar mutlaka 28 farklı şarkı anlamına gelmez; aynı şarkının farklı sürümleri olabilir.

| Ölçüm | Sayı |
|---|---:|
| Kelime zamanı olmayan satır | 71 |
| Bitişi başlangıcına eşit veya küçük kelime | 45 |
| Önceki kelimeyle zaman çakışması | 133 |
| 600 ms üzerinde kelimeler arası es | 35 |
| İlk kelimeden önce 50 ms üzeri satır boşluğu | 46 |
| Son kelimeden sonra 50 ms üzeri satır boşluğu | 86 |

Çakışma, çoklu vokalde bilinçli olabilir; tek başına tanıma hatası sayılmaz. Ancak mevcut ardışık ASS oluşturucu bu durumu açıkça ele almıyor. Baş ve son boşlukları da geçerli olabilir; sorun, bunların otomatik ölçeklemeyle değiştirilmesi. Kayıtların çoğu düzenlenmiş olarak işaretlendiğinden bu sayılar Whisper'ın ham doğruluğunu ölçmez.

Mevcut 35 ASS dosyasında 975 aktif satır bulundu ve tamamında `\kf` var. Bu, dolgu mekanizmasının mevcut olduğunu gösterir; sesle doğru eşleştiğini kanıtlamaz.

## Önerilen düzeltme sırası ve kabul ölçütleri

1. **Elle verilen zamanları koru.** Otomatik kayıt sorununu, dışa aktarım öncesi ölçeklemeyi ve JSON veri kaybını düzelt. Düzenlenen değer yeniden açmada ve video isteğinde değişmemeli.
2. **ASS zaman çizelgesini düzelt.** Baş boşluğu, kısa/uzun es ve uzun tutulan kelime senaryolarında çıktı zamanları, tek seferlik santisaniye yuvarlaması dışında girdiye uymalı.
3. **Önizlemeyi güvenilir yap.** Düzenlerken ses tekrar yüklenmemeli; önizleme ve video aynı zamanları kullanmalı. İşaretleme sırasında doğrudan ses saati okunmalı.
4. **Veri doğrulaması ekle.** Sıfır/negatif süreler, metin-kelime uyumsuzluğu ve desteklenmeyen çakışmalar görünür olmalı; sessizce uydurulan zamanlar doğru ölçüm gibi saklanmamalı.
5. **Gerçek hizalamayı ekle.** Türkçe, hızlı söz, uzun hece, enstrümantal giriş ve geri vokal içeren kısa örneklerde elle etiketlenmiş referansla karşılaştır. Başlangıç/bitiş hatalarını ve manuel düzeltilen kelime oranını ölç.

Tam otomatik hece dolgusuna ilerlemek için yalnızca kelime sınırları da her zaman yeterli değildir: mevcut `\kf` bir kelimenin görsel genişliği boyunca doğrusal ilerler. Bir hecenin uzun tutulduğu yerlerde daha doğal dolgu için ileride hece/fonem sınırları değerlendirilebilir. Önce mevcut kelime zamanlarının korunması gerekir; aksi halde daha iyi hizalama verisi de sonraki aşamalarda bozulur.
