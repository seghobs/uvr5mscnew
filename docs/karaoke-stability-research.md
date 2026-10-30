# Karaoke kararlılığı — araştırma ve uygulama kararları

Tarih: 30 Ekim 2026. Kapsam: kayıt bütünlüğü, verilen sözlerin hizalanması,
otomatik eklemeler, belirsizlik ve hatalı ek model çıktısından geri dönüş.
Hiçbir şarkıda sıfır tanıma hatası garantisi veya ölçülmüş bir doğruluk artışı iddiası yoktur.

## Kaynaklar ve sonuçları

1. [RFC 9110, §13.1.1](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.1):
   kayıp güncellemeleri önlemek için koşullu yazma gerekir. Bu uygulama JSON
   `expected_revision` alanını kullanır; bu bir HTTP ETag uygulaması değildir.
   Uyuşmazlık 409, mevcut kayda sürümsüz yazma 428 döndürür.
2. [SQLite transaction](https://www.sqlite.org/lang_transaction.html) ve
   [isolation](https://www.sqlite.org/isolation.html): ayrı süreçler arasında
   uygulama içi kilit yeterli değildir. `BEGIN IMMEDIATE` içinde sürüm karşılaştırma,
   geçmişe alma ve bütün vokal/enstrümantal takma adlarının güncellenmesi yapılır.
   Sürüm her yazmada artar; saniye çözünürlüklü tarih ve içerik hash'i kullanılmaz.
3. [WhisperX, Interspeech 2023](https://www.isca-archive.org/interspeech_2023/bain23_interspeech.pdf):
   ses etkinliği ile bölütleme ve fonem hizalaması birlikte kullanılır. Buradaki
   uygulama şüpheli bölgelere sınırlı tekrar analizi yapar; konuşma deneylerini
   Türkçe/Kurmancî şarkı doğruluğu olarak sunmaz.
4. [Whisper non-speech hallucinations](https://arxiv.org/abs/2501.11378):
   konuşma olmayan sesler yanlış metin üretebilir. Yeniden dinleme verilen
   sözlerle yönlendirilmez; önceki metin koşullaması kapalıdır. Tek tanıma veya
   tekrar eden aynı model bağlamı tek başına doğrulama sayılmaz. Vokal ve orijinal
   kayıt iki görünüm olarak kullanılır; istatistiksel bağımsızlık iddiası yoktur.
5. [CTC label priors](https://arxiv.org/abs/2406.02560): CTC'nin keskin olasılık
   dağılımı kelime sınırlarını bozabilir. Güven puanı kesin doğruluk değildir.
   Uzayan son kelime ve sonraki satırın ilk kelimesi birlikte kontrol edilir;
   uyuşmayan öneriler uygulanmaz. Bu makaledeki eğitim yöntemi burada uygulanmadı.
6. [TorchAudio alignment API](https://github.com/pytorch/audio/blob/main/examples/tutorials/ctc_forced_alignment_api_tutorial.py):
   kullanılan hizalama API'leri sonraki sürümlerde kaldırılmıştır. Bu çalışma
   sırasında çalışan eşleşmiş torch/torchaudio 2.7.0+cu128 sürümleri yükseltilmedi.

## Uygulanan korumalar

- Kalıcı SQLite sürümü GET ve başarılı kayıt cevabında döner. Kaydın eski olması,
  aynı saniyede değişmesi veya metnin önceki hâline dönmesi yazma korumasını aşmaz.
- Arka plan görevleri de başladıkları sürüme koşullu yazar. Eski editörün manuel
  kaydı, otomatik kaydı, toplu silmesi veya proje içe aktarması yeni kaydı sessizce ezemez.
- Taslaklar temel aldıkları sürümü taşır. Farklı sürümün taslağı otomatik uygulanmaz;
  diskte ayrı korunur, arayüzden JSON indirilebilir ve proje arşivine dahil edilir.
- Çakışmada güncel kaydı yüklemek için görünür bir işlem vardır. Tekrar deneme
  hiçbir zaman güncel sürümü getirip eski düzenlemeyi zorla üzerine yazmaz.
- Başarısız kayıt altyazı dosyalarını değiştirmez. Başarılı kayıt sonrası türetilen
  LRC/SRT dosyaları atomik değiştirilir. SQLite esas kayıttır.
- Ek model aşamaları kopyada çalışır. Kilit, elle bağlanan kelime, verilen metin,
  satır kimliği/sırası ve yeni zaman çakışmaları denetlenir. Başarısız aşamanın
  kısmi çıktısı atılır; uyarı raporlanır. Görev iptali bu geri dönüşte yutulmaz.
- Belirsiz kelimeler yalnızca kurulu Whisper modelleriyle tekrar dinlenir.
  En fazla 12 yerel pencere, pencere başına en fazla 35 saniye kullanılır;
  tüm şarkıdaki yersiz bir hece için sınırsız tarama ve gizli model indirme yapılmaz.
- Süresiz satır geçmiş bir müzik boşluğunu yeniden kullanamaz. SOLO için vokal
  vetosu ve eşlik etkinliği gerekir. Uzayan vokal sessizlik veya sonraki satırla
  karıştırılmamalıdır; kesin olmayan satır geçişi kontrol işaretini korur.
- Son kalite raporu eksik, kontrol bekleyen, tahmini ve yapısal hatalı kelimeleri
  ayırır. Tahmini zamanlar ölçülmüş zaman olarak yeniden etiketlenmez.

## Doğrulama ve sınırlar

`tests/test_karaoke_api.py`: gerçek SQLite ve izole HTTP üzerinde aynı sürümle
yarışan yazıcılar, stem takma adları, sürümsüz istek, ABA, geçmiş ve altyazı koruması.
`tests/test_karaoke_quality.py`: kısmi model hatası, çakışma, NaN, metin kaybı,
kilit/manuel koruması, iptal ve tahmini sonuç raporu.
`tests/test_recognition_support.py`: bağımsız tanıma kanıtı, yanlış/distant metin,
sınırlı yeniden deneme, yönlendirmesiz iki model testi.
Diğer regresyonlar: uzayan hece/satır geçişi, SOLO çoğalması, tekrar çıkarımı,
çevrimdışı taslak, kayıt kuyruğu, sözcük bağlantıları, oynatma ve içe/dışa aktarma.

Sentetik ve birim testler bütün şarkılarda akustik doğruluğu kanıtlamaz. Gerçek
şarkı kayıtlarının salt okunur kalite taraması yalnızca yapısal tutarlılığı ölçer.
Yüzde doğruluk iddiası için insan tarafından zamanlanmış, farklı türler/diller ve
görülmemiş şarkılar içeren ayrı bir değerlendirme kümesi gerekir.
