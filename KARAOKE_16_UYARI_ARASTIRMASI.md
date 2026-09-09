# Karaoke güven uyarıları: 16 kelimenin nedenleri ve çözüm planı

## Sonuç

Kalan 16 uyarı tek bir sorunu temsil etmiyor. Sekiz kelimenin sınırları farklı ses pencereleriyle yapılan denemelerde görece kararlı kaldı; diğer sekizinde başlangıç veya bitiş belirgin değişti. En öncelikli inceleme alanları girişteki iki “HAA”, ikinci “UYAN”, satır sonunda kalan “İNADINI” ve kapanışta kayıtlı dört kelimelik teşekkür cümlesidir.

Mevcut güven skoru, kelimenin zamanlamasının doğru olma olasılığı değildir. Kod, CTC harf skorlarının aritmetik ortalamasını hesaplıyor ve 0,5'in altını işaretliyor. Bu eşik Türkçe şarkılarda elle doğrulanmış sınırlarla kalibre edilmedi. Düşük skor, doğru ama zor söylenen bir kelimede de; yanlış metin zorla sese yerleştirildiğinde de oluşabilir.

Önerilen çözüm, yalnızca güven eşiğini düşürmek veya aynı düğmeyi tekrar tekrar çalıştırmak değildir. Önce metnin sesle uyuşması, sonra başlangıç/bitiş kararlılığı, ardından uzayan sesin tamamının kapsanması denetlenmelidir. Uyarılar bu nedenlere göre ayrılmalı; yalnızca gerçekten belirsiz bölümler yeniden işlenmelidir.

## İncelenen kayıt ve ölçümün kapsamı

İnceleme `Ensemble_Vocals_1788641882.flac` kaydı ve veritabanının 9 Eylül 2026, 14:40:11 kayıt damgalı söz verisi üzerinde yapıldı. Bu kayıtta yapısal zamanlama hatası bulunmadı: sıfır süre, kelime çakışması ve satır dışına taşma denetimleri geçti. Uyarıların tamamı mevcut CTC inceleme işaretlerinden geliyordu.

Her uyarılı satır, mevcut kayıtlı sonucuna ek olarak iki kez analiz edildi: satırın önüne ve arkasına 0,4 saniye, ardından 1,2 saniye bağlam eklenerek. Kelime metni değiştirilmedi. Tablodaki farklar, kayıtlı sonuç ile iki yeni sonuç arasındaki en büyük ve en küçük başlangıç/bitişin farkıdır. Bu ölçüm **bağlama duyarlılığı** gösterir; gerçek ses sınırından kaç milisaniye sapıldığını göstermez.

Üç sonuç aynı model ailesinden ve aynı ses kaydından gelir; bağımsız üç doğrulayıcı değildir. Üçü de aynı yanlış sınırda birleşebilir. “40 ms altında” ifadesi bu raporun bulguları gruplamak için kullandığı betimsel sınırdır; doğruluk onayı veya üretime alınmış yeni eşik değildir. Uyarıları azaltmak amacıyla kayıtlar, eşikler veya model sonuçları değiştirilmedi.

## Kelime bazında bulgular

Skorlar 0–1 aralığındadır; yüzde doğruluk olarak okunmamalıdır. Satır numaraları incelenen kayıt anına aittir.

| Satır / kelime | Metin | Kayıtlı skor | Başlangıç farkı, ms | Bitiş farkı, ms | Öncelikli değerlendirme |
|---|---|---:|---:|---:|---|
| 1 / 1 | HAA | 0,019 | 16,6 | 209,2 | Vokalizasyon; bitiş güvenilir değil |
| 1 / 2 | HAA | 0,051 | 27,8 | 757,6 | Vokalizasyon; uzama ayrıca ölçülmeli |
| 4 / 5 | OLDU | 0,413 | 15,5 | 17,8 | Düşük skor, kararlı sınırlar |
| 6 / 1 | YÜREĞİMİN | 0,362 | 25,2 | 12,6 | Düşük skor, kararlı sınırlar |
| 13 / 4 | BENİ | 0,492 | 20,0 | 20,1 | Eşiğe yakın, kararlı sınırlar |
| 16 / 4 | BENİ | 0,471 | 20,0 | 0,1 | Eşiğe yakın, kararlı sınırlar |
| 17 / 1 | SÖYLEDİ | 0,459 | 36,5 | 12,6 | Sınırlar kararlı; sözcüğün kendisi ayrıca doğrulanmalı |
| 20 / 4 | UYAN, | 0,489 | 8,6 | 13,1 | İlk tekrar görece kararlı |
| 20 / 5 | UYAN | 0,390 | 6,5 | 1.200,0 | İkinci tekrarın bitişi pencereye duyarlı |
| 22 / 6 | İNADINI | 0,435 | 60,4 | 459,8 | Satır sonu etkisi; sonraki satırla birlikte incelenmeli |
| 23 / 2 | DA | 0,455 | 19,7 | 0,6 | Kısa kelime, kararlı sınırlar |
| 24 / 3 | OLDU | 0,389 | 39,0 | 6,8 | Düşük skor, kararlı sınırlar |
| 27 / 1 | İZLEDİĞİNİZ | 0,174 | 259,1 | 1.200,9 | Metin-ses uyuşmazlığı şüphesi yüksek |
| 27 / 2 | İÇİN | 0,019 | 1.500,9 | 980,5 | Metin-ses uyuşmazlığı şüphesi yüksek |
| 27 / 3 | TEŞEKKÜR | 0,067 | 1.120,6 | 1.200,0 | Metin-ses uyuşmazlığı şüphesi yüksek |
| 28 / 1 | EDERİM. | 0,490 | 156,8 | 898,0 | Skor eşiğe yakın olsa da sınırlar kararsız |

“BENİ” ile “EDERİM” örnekleri tek skorun neden yetersiz olduğunu gösteriyor. İkisinin skoru yaklaşık 0,49; ancak birinde sınırlar yaklaşık 20 ms değişirken diğerinde bitiş yaklaşık 898 ms değişiyor. Aynı soru işaretinin altında çok farklı inceleme öncelikleri bulunuyor.

## Nedenler

### 1. Harf tanıma skoru ile zamanlama doğruluğu birbirine karıştırılıyor

`karaoke_ctc.py` içindeki `words_from_spans`, kelimenin harf skorlarını ortalayıp `score < .5` koşuluyla inceleme işareti üretiyor. Bu hesap, başlangıç ve bitişin ne kadar kararlı olduğuna bakmıyor. İlk veya son harfin zayıflığı ile ortadaki bir harfin zayıflığı da aynı ortalamaya giriyor.

Eşiği 0,5'ten 0,35'e indirmek bu kayıtta uyarı sayısını 16'dan 5'e düşürür; fakat tek bir ses örneği veya kelime sınırı değişmez. Böyle bir değişiklik, başarılı bir senkron düzeltmesi olarak sunulmamalıdır. Sinir ağlarında güven skorlarının gerçek doğrulukla ilişkilendirilmesi ayrı bir kalibrasyon problemidir; genel kalibrasyon araştırması da ham skorun otomatik olarak doğru olasılık kabul edilemeyeceğini gösterir. Buradaki sınır tespiti görevi için ayrıca etiketli veri gerekir. [Guo ve diğerleri, 2017](https://proceedings.mlr.press/v70/guo17a.html).

### 2. CTC bir harfin tüm ses süresini garanti etmez

Mevcut kod kelimeyi ilk harf aralığının başlangıcından son harf aralığının bitişine kadar alıyor. Ancak CTC çıktısı bir harfin tüm ses süresi boyunca etkin kalmak zorunda değildir. Özellikle uzun ünlülerin sonu, son harf tepesinden sonra devam edebilir; bu durumda kelime erken bitebilir. Sonraki sese kadar otomatik uzatmak ise komşu kelimeyi içeri alabilir.

TorchAudio'nun resmi açıklaması, boş CTC etiketlerinin hem tekrar hem kelimeler arası boşluk için yorumlanabildiğini ve harf tepelerinin harfin bütün süresini kapsamayabildiğini açıkça tartışır. Bu, yalnızca projedeki bir görüntüleme hatası değildir; kullanılan hizalama gösteriminin sınırıdır. Tutorial farklı bir model örneği kullanır; kavramsal sorun bu projede ayrıca ölçülmelidir. [TorchAudio CTC forced alignment: blank token ve tepe davranışı](https://docs.pytorch.org/audio/2.1/tutorials/ctc_forced_alignment_api_tutorial.html#inconsistent-treatment-of-blank-token).

### 3. Konuşma modeli, şarkı söyleyişine tam uyumlu değildir

Kullanılan Türkçe modelin kartında eğitim kaynakları Common Voice 7 Türkçe ve MediaSpeech olarak veriliyor. Karttaki başarı ölçümleri konuşma tanımaya ait; Türkçe karaoke kelime bitişlerinin doğruluğu için bir garanti sunmuyor. Uzatılan ünlüler, müzikal vurgu ve birleşen kelimeler bu nedenle ayrıca sınanmalı. [mpoyraz Türkçe Wav2Vec2 model kartı](https://huggingface.co/mpoyraz/wav2vec2-xls-r-300m-cv7-turkish).

Şarkı hizalamasına özel araştırmalar, yalnızca yazıya dökme için eğitilen CTC yaklaşımının hizalama açısından sınırlı kalabileceğini ele alıyor. Kontrastif ses-metin hizalaması ve perde bilgisini kullanan yöntemler araştırmaya değer alternatiflerdir. Bunların yayın sonuçları bu Türkçe parçadaki başarıya doğrudan aktarılmaz; mevcut sistemle aynı örnekler üzerinde karşılaştırma gerekir. [Durand, Stoller ve Ewert, 2023](https://arxiv.org/abs/2306.07744), [Huang ve diğerleri, 2022](https://arxiv.org/abs/2202.01646).

### 4. Yanlış metin de sese zorla yerleştirilebilir

Hizalayıcı verilen metni doğru varsayar. Metinde seste bulunmayan bir sözcük varsa yine de o sözcüğe harf aralıkları atamaya çalışır. Dolayısıyla zamanların sıralı ve çakışmasız olması, sözlerin doğru olduğunu kanıtlamaz.

Kapanıştaki teşekkür cümlesi en güçlü inceleme adayıdır. Harf modelinin metin zorlanmadan ürettiği ham diziler bu cümleyi açık biçimde desteklemedi; sınırlar da yaklaşık 0,9–1,5 saniye oynadı. Ham CTC metni anlaşılır bir doğru transkript değildir; bundan hareketle cümle otomatik silinmemelidir. Bulgular, kapanışın dinlenerek veya doğrulanmış sözlerle kontrol edilmesi gerektiğini gösterir.

Ek olarak, mevcut Large-V3 modeline söz ipucu verilmeden dört bölge yazıya döktürüldü:

| Bölge | Süre | Modelin verdiği aday |
|---|---|---|
| Giriş | 0–8 sn | “Altyazı M.K.” |
| UYAN çevresi | 88–97 sn | “Altyazı M.K.” |
| İNADINI çevresi | 99–107 sn | “İzlediğiniz için teşekkür ederim.” |
| Kapanış | 126–144,428 sn | “İzlediğiniz için teşekkür ederim.” |

Birbirinden farklı bölgelere aynı kalıp yanıtların gelmesi bu denemeyi güvenilir bir doğrulayıcı olmaktan çıkarıyor. Özellikle modelin teşekkür cümlesini tekrar üretmesi, kapanış metninin doğrulandığı anlamına gelmiyor. Whisper'ın resmi model kartı, seste söylenmeyen metinler ve tekrarlanan çıktılar üretilebildiğini bildirir. Bu kayıttaki davranış o sınırlamayla uyumludur; yine de her bölümün gerçek içeriği yalnızca bu testle kesinleştirilmemiştir. [OpenAI Whisper model kartı: sınırlamalar](https://raw.githubusercontent.com/openai/whisper/main/model-card.md).

### 5. Kesilmiş bağlam, özellikle son kelimeyi etkiliyor

İkinci “UYAN” ve satırın sonundaki “İNADINI”, daha fazla ses eklendiğinde bitişi belirgin değişen örneklerdir. Bu, son kelimenin sonraki sesleri üzerine alma veya pencere kenarına göre bitme ihtimalini gösteriyor. Çözüm bütün kelimeleri aynı miktarda kısaltmak değildir; ilgili kelimeyi bir sonraki sözcüklerle birlikte değerlendirmek gerekir.

Mevcut uygulamanın komşu satırları birlikte hizalaması sayısal çakışmaları azaltmıştır. Buna rağmen grup sınırları kaba Whisper sürelerinden türetilmektedir. Kaba sınır yanlışsa sonraki aşama eksik ses penceresi alabilir. Ayrıca bu araştırmadaki tek satır denemesi üretim akışının yerine önerilmemektedir; özellikle bu zayıflığı görünür kılmak için kullanılmıştır.

## Çözüm sırası

### Önce metin ve ses türü

İlk iş kapanış cümlesinin ve “SÖYLEDİ”, “UYAN” gibi tartışmalı sözlerin doğru metinle karşılaştırılmasıdır. Doğrulanmış metin bir kez belirlenmeli ve sonraki hizalamalar onu yeniden yazmamalıdır. Söylenmeyen bir teşekkür yazısı yalnızca görsel kapanış olarak isteniyorsa karaoke kelime listesine zorlanmamalı; ayrı bir yazı olarak ele alınmalıdır.

“HAA” gibi sözsüz sesler normal kelimeyle aynı harf doğrulamasından geçirilmemelidir. Bunlar için ayrı bir vokalizasyon türü gerekir. Görünen yazı sabit kalabilir; dolgu aralığı sesin başlangıcına, devamına ve bitişine göre belirlenir. Bunun için ses enerjisi tek başına yeterli değildir: nefes, yankı ve müzik sızıntısı da enerji taşır. Vokal etkinliği ve mümkün olduğunda perde sürekliliği birlikte kontrol edilmelidir. Bu, önerilen uygulama tasarımıdır; mevcut projede henüz ayrı bir vokalizasyon modeli yoktur.

### Ardından yalnızca kararsız bölgeleri yeniden işleme

Sekiz kararsız kelime küçük inceleme bölgeleri olarak ele alınmalı. Her bölgede önceki ve sonraki sözleri kapsayan bağlam kullanılmalı; komşu kelimeler sabit ankraj olarak korunmalı. Tekrarlanan kelimeler ayrı sıra numaralarıyla izlenmeli. Alternatif başlangıç ve bitişler ancak metin korunuyor, komşuya taşma oluşmuyor ve ek ses kanıtı destekliyorsa kabul edilmeli.

Başlangıcı kararlı ama bitişi kararsız bir kelimede bütün aralığı yeniden oynatmak yerine yalnızca bitiş araştırılmalıdır. Bu yaklaşım gereksiz düzeltmenin önüne geçer. Uzayan ünlünün sonunu bulurken son CTC harf tepesine ilave olarak vokal sürekliliği incelenmeli; tüm sessizliği kelimeye eklemekten kaçınılmalıdır.

### Sonra uyarıların anlamını düzeltme

Tek bir “?” yerine en az dört farklı neden saklanmalıdır: düşük harf skoru, kararsız başlangıç/bitiş, metin-ses uyuşmazlığı şüphesi, kullanıcı düzenlemesi sonrası yeniden hizalama ihtiyacı. Vokalizasyon da ayrı tür olmalıdır. Başlangıç ve bitiş güveni ayrı tutulmalı; bir kelimenin başının kararlı olması sonunun da kararlı olduğu anlamına gelmemelidir.

Bu kayıttaki sekiz kararlı kelime için “düşük skor, sınırları kararlı” bilgisi daha doğru bir açıklamadır. Bunları otomatik olarak kesin doğru ilan etmek yerine düşük öncelikli inceleme grubuna almak uygundur. Kullanıcı dinleyerek doğruladığında bu karar metin, ses dosyası ve zaman aralığına bağlı olarak saklanmalı; yalnızca yeniden açma veya büyük harf dönüşümüyle kaybolmamalıdır. Ses ya da zaman aralığı değişirse doğrulama geçersizleşmelidir.

## Kabul ölçütleri

Uyarı sayısının azalması başarı ölçütü olmamalıdır. Başarı, komşu kelimenin duyulmaması, kelimenin başlangıç veya son hecesinin kesilmemesi ve dolgunun sesle uyuşması üzerinden ölçülmelidir. Deneme için mevcut 16 kelimeye ek olarak normal, kısa, uzun ünlülü ve tekrarlanan kelimelerden bir referans kümesi hazırlanmalıdır.

Bu örneklerin başlangıç ve bitişleri dalga biçimi/spektrogram ve dinleme ile işaretlenmelidir. Belirsiz ortak ses geçişlerinde tek bir tartışmasız milisaniye varmış gibi davranılmamalı; kabul edilebilir aralık kaydedilmelidir. Ardından başlangıç/bitiş hatalarının medyanı, üst yüzdelikleri, komşu sözcük sızıntısı ve hece kesme sayısı raporlanmalıdır. 40 ms bağlam kararlılığı veya 0,5 skor eşiği böyle bir değerlendirme yapılmadan doğruluk standardına dönüşmemelidir.

Yeni bir model ancak bu aynı referans kümesinde mevcut modele üstünlük gösterirse kullanılmalıdır. Türkçe konuşma desteği bulunması, Türkçe şarkı sınırlarında daha iyi olacağını tek başına göstermez. Mevcut verilerle daha büyük bir Whisper modelini tekrar çalıştırmak veya güven eşiğini azaltmak öncelikli yatırım değildir.

## Önerilen karar

Öncelik, kapanıştaki dört kelimenin metnini doğrulamak ve girişteki iki “HAA”yı vokalizasyon olarak ele almaktır. Sonra ikinci “UYAN” ile “İNADINI” için bitiş odaklı, komşu sözlerle birlikte yerel hizalama yapılmalıdır. Diğer sekiz kelime, ölçülen kararlılıkları gösterilerek daha düşük öncelikli incelemeye alınabilir. Bunların hepsini aynı soru işaretiyle ve aynı aciliyetle göstermek mevcut kanıta uygun değildir.

Bu araştırmada üretim ayarları ve kayıtlı sözler değiştirilmedi. Sonuç, 16 kelimenin tamamının düzeldiği iddiası değil; sekiz kararlı örneği sekiz daha sorunlu örnekten ayıran ölçüm ve uygulanabilir bir düzeltme sırasıdır.

## Kanıt dosyaları ve kaynaklar

Yerel kayıt anlık görüntüsü, 16 kelimenin alternatif zamanları ve ham model çıktıları `tests/.artifacts/confidence_audit/` klasöründedir. `audit.json` bağlam karşılaştırmasını; `transcript_hypotheses.json` dört bölgenin ipucusuz Whisper çıktısını içerir. Bu veriler elle doğrulanmış söz veya zaman referansı değildir. Yeniden üretim için `tests/audit_low_confidence.py` ve `tests/audit_transcript_candidates.py` kullanıldı.

Kaynaklar 9 Eylül 2026 tarihinde incelendi:

1. PyTorch / TorchAudio. [CTC forced alignment API tutorial — blank token davranışı](https://docs.pytorch.org/audio/2.1/tutorials/ctc_forced_alignment_api_tutorial.html#inconsistent-treatment-of-blank-token). Sürüm 2.1 dokümantasyonu; kavramsal açıklama için kullanıldı, kurulu 2.7 API'si yerel kaynaktan kontrol edildi.
2. mpoyraz. [wav2vec2-xls-r-300m-cv7-turkish model kartı](https://huggingface.co/mpoyraz/wav2vec2-xls-r-300m-cv7-turkish). Eğitim alanı ve model kapsamı. Yerel model revizyonu `708639f50559d7970f462e13ec64d3f059ca89f6`.
3. OpenAI. [Whisper model kartı](https://raw.githubusercontent.com/openai/whisper/main/model-card.md). Seste olmayan metin ve tekrarlanan çıktı sınırlamaları.
4. Guo, Pleiss, Sun ve Weinberger. [On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html), ICML 2017. Ham güven skorları ile doğruluk olasılığının ayrılması.
5. Durand, Stoller ve Ewert. [Contrastive Learning-Based Audio to Lyrics Alignment for Multiple Languages](https://arxiv.org/abs/2306.07744), ICASSP 2023. Şarkı hizalamasına özel alternatif yaklaşım.
6. Huang ve diğerleri. [Improving Lyrics Alignment through Joint Pitch Detection](https://arxiv.org/abs/2202.01646), 2022. Perde ve sınır bilgisinin hizalamaya katılması.
