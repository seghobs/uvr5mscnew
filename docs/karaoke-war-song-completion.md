# Dil Disoje: kalan kelime ve 33 uyarının incelenmesi

Bu çalışmadaki ek denemeler daha sonra genel uygulama akışına taşındı:
[kalıcı otomatik onarım ve kontrolleri](karaoke-permanent-automatic-recovery.md).

31 Ekim 2026. Kayıt: `AtlasStudio_Vocals_0e450a0a9820.wav`.

## Kaydedilen sonuç

- Revizyon 4 → 5; kayıt yeniden API üzerinden okunarak kontrol edildi.
- Özgün 16 söz satırı kimliği korundu. Noktalama sonrası eksik boşluklar
  düzeltildi; sözlerin harfleri ve sırası değiştirilmedi.
- 34 söylenen satır, 11 müzik etiketi; toplam 45 satır.
- 102/102 söylenen kelimenin pozitif zaman aralığı var. Eksik kelime,
  tahmini kelime, editör uyarısı, yapısal çakışma ve oluşturma hatası yok.
- LRC/SRT dosyaları yeniden üretildi. Önceki kayıt çalışma yedeğinde tutuldu;
  kaydetme öncesi revizyon ve tüm içerik karşılaştırılarak yeni kullanıcı
  düzenlemelerinin üzerine yazılmadığı doğrulandı.

Kelime sayısı önceki 98 ile aynı payda değildir: boşluksuz
`disoje,diqîre` ayrı kelimelere ayrıldı ve atlanan son nakarat tamamlandı.
Bu nedenle sonuç bir doğruluk yüzdesi karşılaştırması olarak sunulmaz.

## Nedenler ve düzeltmeler

1. **Nakaratın müzik arasına taşması.** Eksik kelime, yanlış yere konmuş
   otomatik tekrarın içindeydi. Gerçek tekrarların kelime ve dalga biçimi
   araması yerleşimi değiştirdi. 160–211 saniye arasındaki çalgısal bölümde
   zorla sözcük hizalanmadı. 18 saniyeye yayılmış `heval` doğru nakaratın
   yaklaşık 135.856–137.056 saniye aralığına taşındı.
2. **Virgülle ayrılan parçalarda gerçek bekleme.** Parçalar içeride ayrı
   aranıyor, sonra aynı kaynak kimliği ve tam metinle birleştiriliyor.
   Kısa nakaratın en yakın uygun örneği seçiliyor; uzak bir örnekle aradaki
   müzik doldurulmuyor. Noktalama boşluğu farklı satırların ortak akustik
   sonuçları, her satırın kendi sözcüklerine tekrar eşleniyor.
3. **Zayıf duyulan son tekrar.** Daha uzun nakaratın içindeki ölçülmüş kısa
   nakarat da dalga biçimi karşılaştırmasına kaynak olabiliyor. Bu yolla
   bulunan ön parça, bağımsız bulunmuş son parçayla seçimden önce yeniden
   birleştiriliyor. Son 332–340 saniye dönüşü bu şekilde de bulunabiliyor.
4. **Kısa sözcükte sıfır MFCC vektörü.** Birkaç sessiz çerçeve bütün kelime
   karşılaştırmasını geçersiz kılıyordu. Kısa sessizlik artık ayrı bir
   koordinatla, kendi süresi korunarak temsil ediliyor. Tam sessizlik ve
   uzun iç boşluk veto koşulları korunuyor; zaman sıkıştırılmıyor.
5. **Yankının yeni uyarı üretmesi.** İki model mevcut bitişi doğruladığında,
   desteklenmeyen enerji kuyruğu mevcut zamanı geçersiz kılmıyor. Önceden
   bulunan başka uyarı silinmiyor; desteklenmeyen uzatma uygulanmıyor.

## Sözcük kanıtları

Aynı orijinal `Dil Disoje.wav` dosyası, vokal + enstrümantal toplamıyla
0.9999999999999976 korelasyonla eşleşti. Vokal ve orijinal ses; Kurmancî MMS,
Kurmancî CV8, Türkçe CV7/CV8 ve ayrıca kurulu eski Kurmancî CV7 modeliyle
ölçüldü. Eski Kurmancî CV7 bu kayıtta yeterli sonuç vermedi; oyu doğrulama
kanıtı sayılmadı. Aynı modelin bağlam tekrarları ayrı model oyu sayılmadı.

- 90 kelime farklı modellerin sınırlı zaman uzlaşmasıyla yerleştirildi.
- 10 kelimede CTC sınırlarına, aynı kayıttaki güvenilir örneklerle DTW
  karşılaştırması ve farklı sözcüklerle negatif karşılaştırma eklendi.
  Zaman değiştikten sonra akustik karşılaştırmalar yeniden yapıldı. İzole
  ses sınıfı belirsizleşen bir `Dil`, tam nakarat ve negatif ikili sözcük
  örnekleriyle ayrıca kontrol edildi.
- Son iki kelimede tüm ifadenin pozitif/negatif karşılaştırması ve süreyi
  koruyan DTW sınır aktarımı kullanıldı. `kûr` ifadesinde aynı ifade maliyeti
  0.148, en yakın farklı ifade 0.211; `heval` ifadesinde 0.038 ve 0.324.
  Önceki `<0.20` ve farklı örneğe göre `<0.75` koşulları değiştirilmedi.
  Aktarılan sınırların yerel CTC ölçümlerine yakınlığı ayrıca kontrol edildi.

Güven puanları yükseltilmedi; işlemler insan tarafından dinlenmiş gibi
`manual` olarak işaretlenmedi. Sözcüklerde kullanılan kanıt ve önceki
sınırlar `timing_reference` içinde saklandı. Bu, **akustik/model doğrulamasıdır**;
insan referansıyla ölçülmüş yüzde 100 doğruluk veya bütün şarkılar için
hatasızlık garantisi değildir.

## Kontroller

493 Python testi, 20 frontend test dosyası ve TypeScript kontrolü başarılı.
Güncel üretim derlemesi çalışıyor. Yeni genel tekrar aramasının gerçek kayıt
çıktısı, özgün 16 satırlık görüntüye karşı arayüzün metin/kimlik koruma
kontrolünden geçti. Son kayıtta tüm editör ve oluşturma kontrolleri temiz.

[Makine tarafından okunabilir kayıt özeti](karaoke-war-song-completed-validation.json)
