# Karaoke kelime zamanlaması: araştırma, düzeltmeler ve doğrulama

## Sonuç

Sürekli elle düzeltme ihtiyacının önemli bir kısmı, ölçülen kelime zamanlarının uygulamanın sonraki aşamalarında yeniden hesaplanmasından kaynaklanıyordu. Ses analizi bir kelime için doğru sınır üretse bile satır düzenleme, kayıt ve video üretimi bu sınırları değiştirebiliyordu. Kelime önizlemesinde oynatmayı durdurmak tarayıcı olaylarına bağlıydı; dolayısıyla seçilen aralıktan sonra komşu kelime de duyulabiliyordu.

Bu davranışlar değiştirildi. Ölçülen zamanlar artık düzenleme, kayıt, JSON aktarımı ve video üretimi boyunca korunuyor. Kelime önizlemesi yalnızca seçilen aralığın ses örneklerini içeren ayrı bir tampon çalıyor. Renklendirme kelimenin kendi başlangıç ve bitişine bağlı; kelimeler arasındaki sessizlik bir sonraki kelimeye dağıtılmıyor.

Ancak bunlar, ses modelinin her kelime sınırını kesin doğru bulduğunu kanıtlamaz. Gerçek vokal örneğinde iki ayrı modelle yapılan denemeler belirsiz sınırlar üretti. Bu nedenle tüm şarkılarda sıfır elle müdahale ve gerçek ses başlangıcına bir milisaniye doğruluk sağlandığı iddia edilemez. Uygulama bilinen belirsizlikleri işaretliyor ve bu durumlarda video üretimini engelliyor; yüksek model güveni de tek başına akustik doğruluk garantisi değildir.

## Sorunun kaynakları

| Aşama | Önceki davranış ve sonucu | Uygulanan değişiklik |
|---|---|---|
| Satır düzenleme | Kelime sürelerini satır aralığına yeniden ölçeklemek, doğru sınırları kaydırıyordu. | Zamanlar aynen korunuyor; satır dışına çıkan veya metinle uyuşmayan veri görünür hata oluyor. |
| Video altyazısı | Süreler yeniden paylaştırılıyor; sessizlikler kısaltılıyor veya başka kelimeye aktarılıyordu. | Mutlak kelime başlangıçları ve bitişleri kullanılıyor; boşluklar ayrı bekleme süreleri olarak yazılıyor. |
| Otomatik kayıt | Düzenlenen listeye bağlı kapanış işlemi yeni kaydı iptal edip eski görüntüyü kaydedebiliyordu. | Güncel veri anlık görüntüsü ve sıralı kayıt kuyruğu; pencere kapanırken son bekleyen kayıt gönderiliyor. |
| Kelimeye tıklama | Genel ses oynatıcısını başlatıp daha sonra durdurmak, olay gecikmesinde komşu kelimeyi duyuruyordu. | Yalnızca seçilen ses örnekleri kopyalanıp çalınıyor; hızlı ardışık tıklamalarda eski istek iptal oluyor. |
| Metinden hizalama | Metnin ilk 350 karakterini modele ipucu vermek, tam metni sesle eşleştirmiyordu. | Verilen sözlerin tamamı mevcut vokalle zorunlu hizalamaya giriyor. |
| Ses yaşam döngüsü | Her söz düzenlemesi ses dosyasını yeniden yükleyebiliyordu. | Yükleme yalnızca pencere ve ses kaynağı değiştiğinde yapılıyor. |
| Dosya aktarımı | JSON aktarımında kelime sınırları kaybolabiliyordu. | Kelimeler, sınırlar, güven bilgisi ve inceleme durumu korunuyor. |
| Görsel ilerleme | Satırın toplam süresine göre dolan alan, kelimenin gerçekten okunmasını temsil etmiyordu. | Her kelimenin kendi zaman aralığına bağlı ayrı renk dolgusu gösteriliyor. |
| Uzun işler | Bekleme süresi ve görev temizliği, devam eden işlemleri tamamlanmadan kaybettirebiliyordu. | Devam eden görevler temizlenmiyor; hizalama ve uzun video işleri için bekleme süresi genişletildi. |

Ön incelemede veritabanındaki 100 kayıt, aynı içerikleri tekilleştirince 28 farklı söz verisine karşılık geldi. Bunlarda 802 satır ve 3.858 kelime; kelimesiz 71 satır, sıfır/negatif süreli 45 kelime ve 133 çakışma bulundu. Bu sayılar kayıt yapısındaki sorunları gösterir; elle doğrulanmış ses referansı olmadığı için model hata oranı olarak yorumlanamaz. Ayrıntılı önceki değerlendirme [KARAOKE_ZAMANLAMA_ANALIZI.md](./KARAOKE_ZAMANLAMA_ANALIZI.md) dosyasındadır.

## Otomatik hizalama seçimi

Metni tanımak ile bilinen sözleri ses üzerine yerleştirmek ayrı problemlerdir. Seçilen akış, sözler bilinmiyorsa önce yazıya döküyor; ardından tam metni vokalle hizalıyor. Sözler yapıştırılmışsa metni yeniden tahmin etmek yerine verilen metni kullanıyor. Sonuçta kelime kaybı varsa eski kaydı değiştirmeden hata veriyor.

Mevcut Faster Whisper modelleriyle çalışabildiği için stable-ts hizalama yolu seçildi. `stable-ts==2.19.1` ve `faster-whisper==1.2.1` bağımlılıkları sabitlendi. Mevcut CUDA/PyTorch düzenini değiştirmeden hem `large-v3-turbo` hem `large-v3` ile çalışması denendi. stable-ts, mevcut metinle hizalama ve sessizliğe göre zaman düzeltme işlevleri sunuyor. Bu özellikler doğruluk garantisi olarak yorumlanmadı. [stable-ts, proje belgeleri](https://github.com/jianfch/stable-ts) ve [hizalama uygulaması](https://raw.githubusercontent.com/jianfch/stable-ts/main/stable_whisper/alignment.py).

WhisperX de değerlendirildi. Ayrı fonem hizalama modeli kullanan yaklaşımı bu problem için anlamlı bir alternatiftir; Türkçe için dil modeline ilişkin eşleme de bulunuyor. Ancak bu projede yeni bir model yığını eklemek yerine çalışan modellerle doğrulanabilir bir düzeltme tercih edildi. WhisperX'in bu şarkılarda daha doğru olduğu ölçülmedi; burada karşılaştırmalı başarı iddiası yoktur. [WhisperX makalesi, Bain ve diğerleri, 2023](https://arxiv.org/abs/2303.00747) ve [WhisperX kaynak kodu](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py).

Sıfır süreli veya düşük güvenli kelimeler silinmiyor; inceleme gerekli olarak saklanıyor. Kullanılan 0,35 güven eşiği bir koruma kuralıdır, kalibre edilmiş doğruluk yüzdesi değildir. Hızlı eşit/hece dağıtımı seçenekleri taslak olarak etiketlendi; bunlardan üretilen tahmini zamanlar doğrulanmadan videoya gidemiyor. Modelin yanlış ama yüksek güvenli sınır üretme ihtimali ise sürüyor.

## Zamanlama sözleşmesi

Her kelime tek bir başlangıç ve bitiş çifti taşıyor. Kaydetme, pencereyi yeniden açma, dışa aktarma ve video üretimi bu çifti yeniden dağıtmıyor. Bir satırın metni değiştirilirse önceki zamanların yeni metne uyduğu varsayılmıyor. Satır sınırları değiştirilirse kelimeler otomatik sıkıştırılmıyor; uyuşmazlık açıkça bildiriliyor.

Önizleme dolgusu başlangıçtan önce sıfır; başlangıç ile bitiş arasında doğrusal; bitişten sonra tam dolu. Sessizlik sırasında sonraki kelime dolmaya başlamıyor. Dolgunun kelime içinde doğrusal ilerlemesi, fonemlerin veya hecelerin gerçek sürelerinin ayrı ayrı ölçüldüğü anlamına gelmez. Uzatılan bir heceye göre kelime içi hız değiştirmek ayrı bir fonem/hece hizalaması gerektirir.

Kelime önizlemesi vokal dosyasını kullanıyor. Başlangıç örneği yukarı, bitiş örneği aşağı yuvarlanarak belirtilen aralığın dışındaki örnekler kopyalanmıyor. Böylece uygulama ana iş parçacığı gecikse bile tamponun içinde sonraki kelimeye ait zaman aralığı bulunmuyor. Bunun akustik sınırı doğru bulma sorunundan ayrı olduğu unutulmamalı: model başlangıcı yanlış yerleştirdiyse yanlış yerleştirilmiş aralık çalınır. Web Audio zamanlanmış tampon çalımını destekler; genel `timeupdate` olayının frekansı ise sisteme göre yaklaşık 4–66 Hz olabilir. [MDN: AudioBufferSourceNode.start](https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode/start), [MDN: timeupdate](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/timeupdate_event).

Kelime önizlemesinin görsel saati, desteklenen tarayıcılarda ses çıkış cihazı zamanına bağlandı. Ses işleme tamamlandı diye son pikseller hemen doldurulmuyor; çıkış saati kelime sonuna ulaşana kadar bekleniyor. Bu yaklaşım cihaz tamponlamasından gelen erken görsel bitişi azaltır; işletim sistemi ve fiziksel hoparlör davranışına mutlak garanti vermez. [MDN: getOutputTimestamp](https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/getOutputTimestamp).

## Video zamanlaması ve hassasiyet sınırları

ASS altyazısındaki karaoke etiketleri santisaniye, yani 10 ms birimindedir. Uygulama her mutlak sınırı bir kez yukarı yuvarlıyor; ayrı ayrı süreleri yuvarlayıp biriktirmiyor. Böylece kanonik başlangıçtan erken doldurma ve uzun satır boyunca biriken yuvarlama kayması önleniyor. Kelimeler arasındaki boşluklar boş karaoke heceleriyle korunuyor. [Aegisub: ASS karaoke etiketleri](https://aegisub.org/docs/latest/ass_tags/).

Video 60 kare/saniye üretilecek şekilde güncellendi. Bir karenin süresi yaklaşık 16,67 ms olduğundan dışa aktarılan videoda 1 ms görsel çözünürlük yoktur. ASS yuvarlaması ve kare örneklemesi ideal görüntülemede başlangıcı toplamda yaklaşık 26,7 ms'ye kadar geciktirebilir; bu, model hatası veya video oynatıcısı gecikmesi dahil edilmiş bir uçtan uca hata sınırı değildir.

Yerel Faster Whisper uygulamasındaki zaman hassasiyeti 0,02 saniyedir. Arayüzde üç ondalık basamak göstermek modelin 1 ms doğrulukla ses sınırı ölçtüğü anlamına gelmez. Sayısal saklama hassasiyeti, modelin ölçüm doğruluğu ve görüntü kare hızı ayrı kavramlardır. [Faster Whisper kaynak kodu](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py).

Vokal ile video müziği süreleri arasındaki 20 ms'den büyük farklar da video üretiminden önce kontrol ediliyor. Süreleri aynı olan fakat içerikleri dışarıda kaydırılmış iki dosya bu kontrolle kesin tespit edilemez. Ayrıca üst üste söylenen kelimeler mevcut tek sıra karaoke sözleşmesinde çakışma sayılır; çoklu vokal katmanlarını ayrı satır zaman çizelgelerinde çözmek bu uygulamanın doğrulanmış kapsamı değildir.

## Veri koruması

Kayıt istekleri sırayla işleniyor. Hizalama başladığında kayıt sürümü alınarak sonuç yazılmadan tekrar karşılaştırılıyor. Arada sözler düzenlendiyse eski hizalama sonucu yeni düzenlemeyi ezmiyor. Önceki farklı söz verileri `lyrics_history` tablosunda tutuluyor. Başarısız hizalama mevcut sözleri silmiyor.

Geçersiz veya eksik bir taslağı kaydetmek mümkün; bunları videoya dönüştürmek engelleniyor. Bu ayrım, düzenleme sırasında çalışmanın kaybolmasını önlerken bilinen hatalı sınırların başarılı sonuç gibi sunulmasını önlüyor. İnceleme işaretleri JSON aktarımında da korunuyor.

## Doğrulama sonuçları

| Kontrol | Sonuç | Kapsam sınırı |
|---|---|---|
| Python zamanlama ve API testleri | 19 test başarılı. | API testleri geçici veritabanında gerçek işlevleri yalıtarak çalıştırır; tamamı GPU testi değildir. |
| Mutlak sınır ve yuvarlama | 500 örnek × 20 kelime; toplam 10.000 kelimede birikimli zaman kayması görülmedi. | Üretilmiş sayısal örneklerdir, şarkı doğruluk ölçümü değildir. |
| Ön yüz testleri | Erken dolmama, kayıpsız JSON, sıralı kayıt, yalnızca seçili örnekleri çalma, hızlı tıklama ve iptal başarılı. | Ses cihazı davranışının tüm bilgisayarlarda ölçümü değildir. |
| Üretim derlemesi | Next.js derlemesi ve TypeScript kontrolü başarılı. | İşlevsel ses doğruluğunun yerine geçmez. |
| Tarayıcı kayıt denemesi | İlk kelime başlangıcı 1,251'den 1,301'e değiştirildi; kapatıp açınca 1,301 korundu. İkinci kelime değişmedi. | Ayrı, yapay bir test projesidir. |
| Gerçek video | 60 fps MP4 üretildi; başlangıç öncesi ve kelimeler arası boşlukta erken dolgu görülmedi. | Bilinen sınırlara sahip iki yapay ses aralığıdır. |
| Gerçek vokal, turbo model | 7,87 saniyede 9/9 kelime korundu; 4 kelime incelemeye işaretlendi. | Elle etiketlenmiş doğru zaman referansı bulunmuyor. |
| Gerçek vokal, büyük model | Aynı örnekte 9/9 kelime korundu; bir sıfır süre ve iki düşük güven sorunu bulundu. | Daha büyük modelin bu örnekte kusursuz çözüm olmadığı görüldü. |

Video kontrolünde ilk kelime 1,301–1,751; ikinci kelime 3,004–3,604 aralığındaydı. Sarı piksel sayısı 1,2 ve 1,3 saniyede sıfırdı. İlk kelime tamamlandıktan sonra 1,8, 2,5 ve 3,0 saniyelerde aynı kaldı; ikinci kelime başladıktan sonra yeniden arttı. Bu gözlem, aradaki sessizliğin sonraki kelimeyi erken doldurmadığını destekliyor.

Testler `tests/test_karaoke_timing.py`, `tests/test_karaoke_api.py`, `tests/karaoke_frontend.cjs`, `tests/smoke_alignment.py` ve `tests/verify_karaoke_video.py` dosyalarında bulunuyor. Yerel deneme çıktıları `tests/.artifacts/` altında tutuluyor. Video doğrulaması ayrı `Karaoke_Sync_Test_` dosyalarıyla yapıldı; özgün ses dosyaları değiştirilmedi.

## Kullanım ve kalan doğrulama ihtiyacı

Mevcut projede sözler doğruysa **Kelimeleri otomatik hizala** düğmesi tam metni vokalle eşleştirir. Sonuçta inceleme uyarısı varsa sistem bunu kusursuz zamanlama olarak kabul etmez. Eski kayıtlardaki metin/zaman uyuşmazlıkları da aynı denetimden geçer; yeniden hizalama gerekli olabilir.

Tam otomasyon için kalan kritik çalışma, farklı şarkılardan elle doğrulanmış başlangıç/bitiş örnekleriyle gerçek akustik hata ölçümüdür. Özellikle uzun ünlüler, çok kısa bağlaçlar, tekrar eden sözler, yankı ve üst üste vokaller ayrı değerlendirilmelidir. Bu veri olmadan bir modele veya güven eşiğine yüzde yüz doğruluk atfetmek doğru değildir. Mevcut uygulama, bilinen yazılım kaynaklı kaymaları giderir ve tespit edebildiği belirsizlikleri saklamaz.

## Tekrarlanan “kara kara” örneğinde ek inceleme

`Ensemble_Vocals_1788641882.flac` dosyasındaki ikinci satırda komşu kelimenin duyulması bildirildi. Kaydedilmiş ikinci “kara” aralığı 12,870–13,270 saniyeydi. Oynatıcı bu sayısal aralığı izole etse de bu aralığın akustik olarak tek bir kelimeyi temsil ettiği doğrulanmış değildi. Yüksek Whisper güven puanı da bu ayrımı sağlamadı.

Mevcut modelle kısa satırı yeniden hizalama ve stable-ts refinement denemesi farklı sınırlar üretti; refinement bazı aralıkları genişletti ve bir çakışma da oluşturdu. Bu sonuç otomatik düzeltme olarak uygulanmadı. Tekrarlanan kelimelerin sıralı harf hedefleri üzerinden ayrılmasını denemek için Türkçe Wav2Vec2 CTC modeli yerel olarak çalıştırıldı. Bu model WhisperX'in Türkçe hizalama eşlemesinde de yer alır; şarkı sınırlarında doğruluk garantisi yoktur. [WhisperX dil eşlemesi](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py), [mpoyraz Türkçe model kartı](https://huggingface.co/mpoyraz/wav2vec2-xls-r-300m-cv7-turkish).

| Kelime | Kayıtlı aralık | Deneysel harf hizalaması |
|---|---|---|
| İlk kara | 12,430–12,870 | 12,727–13,068 |
| İkinci kara | 12,870–13,270 | 13,128–13,528 |
| Seni | 13,270–13,810 | 13,589–13,989 |

Yaklaşık 0,26–0,32 saniyelik başlangıç farkları, komşu kelimeden ses duyulmasına yol açabilecek büyüklüktedir. Bunlar bağımsız model tahminleridir; elle doğrulanmış gerçek sınırlar değildir. CTC karakter çıkışları da özellikle kelime sonundaki uzatmaları eksik kapsayabilir. Deneysel sonuçlar ana hizalama yoluna eklenmedi ve kayıtlı sözler değiştirilmedi. Ayrı karşılaştırma klipleri `tests/.artifacts/boundary_probe/ctc_5.wav` ve `ctc_6.wav` dosyalarında tutulur; ilk ve ikinci “kara”yı temsil eder.

Bu incelemede iki bağımsız arayüz hatası da düzeltildi: duraklamış oynatma imleci tam bir sonraki kelimenin başlangıcındaysa sonraki kartın aktif görünmesi; inceleme gerektiren kelimeye tıklama reddedildiğinde önceki kelime/satır sesinin devam etmesi. İkinci durum gerçek tıklama işleviyle regresyon testine eklendi. Ön yüz testleri, 19 Python testi ve üretim derlemesi başarılıdır.

Deneysel model sürümü `708639f50559d7970f462e13ec64d3f059ca89f6` olarak sabitlendi ve `models/alignment/turkish-ctc` içine indirildi. Model kartındaki lisans CC BY 4.0'dır. Ses dosyası dış hizmete gönderilmedi; karşılaştırma yerel olarak yapıldı. Deneyin yeniden çalıştırılması için `tests/probe_word_boundaries.py` ve `tests/probe_ctc_boundaries.py` dosyaları eklendi.

## Üretim akışına entegrasyon ve tam proje testi

Önceki bölümdeki deneysel yöntem artık `karaoke_ctc.py` üzerinden ana hizalama işlemine bağlandı. Türkçe için önce Whisper ile kaba yerleştirme, ardından harf tabanlı CTC hizalaması çalışır. Dolayısıyla otomatik hizalama düğmesine tekrar basmak eski, yalnızca Whisper'a dayanan sınırları son sonuç olarak kaydetmez. Türkçe model eksikse sabitlenmiş sürümü indirilir; diğer dillerin mevcut yolu korunur.

İlk tam proje denemesi, satırları ayrı hizalamanın satır geçişlerinde aynı sesi iki kez sahiplenebildiğini gösterdi. Bunun üzerine komşu satırlar en fazla yaklaşık 18 saniyelik gruplar halinde birlikte hizalandı; grup ses pencerelerinin de birbirine taşması engellendi. Kelimeler, özellikle tekrar eden kelimeler, aynı metne göre sözlük anahtarıyla eşlenmez: her tekrar kendi sıralı harf aralıklarını tüketir. Noktalama dışında modelde temsil edilemeyen karakterler sessizce atılmaz; ilgili grup inceleme gerektirir.

`Ensemble_Vocals_1788641882.flac` projesinin 28 satır ve 131 kelimesinin tamamı bu akışla işlendi. Grup hizalaması sonrası kelime ve satır geçişlerinde zaman çakışması kalmadı. Karakter güven eşiğine göre 15 kelime hâlâ inceleme gerektiriyordu; bu sayının düşük olması veya önceki sayıdan farklı olması tek başına akustik doğruluk artışı ölçümü değildir. Özellikle giriş vokalizasyonları ve düşük güvenli kelimeler kesin doğru ilan edilmedi.

Yeni sonuçlar mevcut projeye API üzerinden kaydedildi. Kaydetmeden önce mevcut kaydın analiz başlangıcındaki veriyle aynı olduğu kontrol edildi; eski veriler ayrıca `tests/.artifacts/ctc_project/before.json` ve veritabanı geçmişinde korunur. Vokal ve enstrümantal adlarıyla yeniden okuma testinde tüm başlangıç/bitiş değerlerinin birebir korunduğu doğrulandı. Örnek satırda yaklaşık yeni aralıklar ilk kara 12,747–13,067, ikinci kara 13,187–13,527, seni 13,587–13,988 saniyedir; yeniden hizalama bağlama göre küçük farklar üretebilir.

Ön yüzde bir başka belirsiz satırın tüm projenin renk dolgusunu sıfırlaması kaldırıldı. Her satır kendi süreleri ve komşu sınırları doğrulandığında dolabilir; belirsiz satırlar ve video üretimi için kontroller korunur. 25 Python/API testi, örnek düzeyinde ses izolasyonunu ve tıklama iptalini kontrol eden ön yüz testleri ve üretim derlemesi başarılıdır. Ek testler tekrarlanan kelimelerin ayrı harf aralıkları tüketmesini ve CTC sonucunun kaba Whisper süreleri yerine kaydedilmesini kapsar.

Son canlı sunucu testinde arayüzün kullandığı `/transcribe_lyrics` isteği, tam metinle baştan sona çalıştırıldı. İş başarıyla tamamlandı; 131 kelime korundu, CTC zamanları kaydedildi ve enstrümantal proje üzerinden aynı sonuç yeniden okundu. Sonuç `tests/.artifacts/ctc_project/live_result.json` dosyasındadır.

Bu entegrasyon, modelin her gerçek ses sınırını kesin bulduğu anlamına gelmez. Sayısal çakışmasızlık, kayıt bütünlüğü ve seçili aralığın dışına çıkmayan oynatma doğrulandı; tüm şarkının elle etiketlenmiş akustik doğruluk ölçümü yapılmış değildir.

## Kaynaklar

Kaynaklar 9 Eylül 2026 tarihindeki inceleme için kullanıldı. Proje depolarının ana dalları zamanla değişebilir; uygulamada kullanılan sürümler ayrıca bağımlılık dosyasında sabitlenmiştir.

1. Jianfch, [stable-ts proje belgeleri](https://github.com/jianfch/stable-ts), [hizalama uygulaması](https://raw.githubusercontent.com/jianfch/stable-ts/main/stable_whisper/alignment.py), [PyPI sürüm kaydı](https://pypi.org/pypi/stable-ts/json).
2. SYSTRAN, [Faster Whisper transcribe.py](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py).
3. Bain ve diğerleri, [WhisperX: Time-Accurate Speech Transcription of Long-Form Audio](https://arxiv.org/abs/2303.00747), 2023; [proje hizalama kaynak kodu](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py).
4. Aegisub, [ASS Tags — karaoke](https://aegisub.org/docs/latest/ass_tags/).
5. MDN Web Docs, [AudioBufferSourceNode.start](https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode/start).
6. MDN Web Docs, [HTMLMediaElement: timeupdate event](https://developer.mozilla.org/en-US/docs/Web/API/HTMLMediaElement/timeupdate_event).
7. MDN Web Docs, [AudioContext.getOutputTimestamp](https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/getOutputTimestamp).
