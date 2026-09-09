# Uçtan uca test sonuçları — 9 Eylül 2026

Testler ayrı üretilmiş sesler ve gerçek vokalin 18 saniyelik test kopyası üzerinde çalıştırıldı. Asıl Hadise kaydı ve sözleri değiştirilmedi. Bu rapor bütün modellerin ve olası her kullanımın hatasız olduğu anlamına gelmez.

## Bulunan ve düzeltilen sorunlar

1. **Perde değişimi tempoyu bozuyordu.** 4 saniyelik test sesi +12 yarım tonda 1 saniyeye, −12 yarım tonda yaklaşık 16 saniyeye dönüşüyordu. Hem tek ses dönüşümünde hem mikste ters oranla tempo telafisi yapıldı. Çıktı uzunluğu hedef örnek sayısına sabitlendi. Sonuç: +12 ve −12 için 4 saniye; 1,25× tempo için 3,2 saniye. Frekanslar da ölçüldü.
2. **Örnekleme hızı bulunamayınca 44,1 kHz varsayılıyordu.** Bu ortamda ffprobe yok. Kaynağın gerçek örnekleme hızı ve süresi SoundFile ile okunuyor. 48 kHz testleri de geçti.
3. **Miks önizlemesi dışa aktarılan sesle aynı perde/tempo işlemini kullanmıyordu.** Önizleme artık aynı sunucu işlemiyle hazırlanıyor; eski ilk-oynatma süresi ve erken bitiş koşulu düzeltildi. Parametre değiştirilirse önceki önizleme durur, yeni ayarlar sonraki oynatmada hazırlanır.
4. **Eksik dosyada başka ses açılabiliyordu.** `Karaoke_Sync_Test_Vocals_missing.wav` isteği yanlışlıkla `Karaoke_Sync_Test_Vocals.wav` döndürüyordu. Benzer isim tahmini kaldırıldı. Unicode/case eşdeğerleri destekleniyor; eksik dosya 404 veriyor.
5. **Söz adayı için süre uyuşmazlığı yeterince korunmuyordu.** En yakın aday bile kayıttan 2 saniyeden fazla farklıysa otomatik seçim yapılmıyor. Arayüzde uyarı doğrulandı; kullanıcı adayı ayrıca seçebilir.
6. **Eski `next lint` komutu çalışmıyordu.** ESLint CLI ve typecheck komutu eklendi. Next ayrıştırıcısıyla uyumsuz çıkan ESLint 10 yerine çalışan 9.39.5 sürümü sabitlendi. Bu sürüm için paket sağlayıcısı destek sonu uyarısı veriyor; ileride Next ayrıştırıcısıyla birlikte yükseltilmeli. React Compiler bu projede etkin olmadığı için geçiş tanıları uyarı seviyesinde görünür durumda tutuldu; hiçbir kural gizlenmedi.
7. Dışa aktarma blob bağlantısı tıklamanın hemen ardından serbest bırakılıyordu; tarayıcının tüketebilmesi için serbest bırakma geciktirildi. Gerçek dosya indirme tamamlanması aşağıdaki sınıra tabidir.
8. Aynı saniyede üretilen ses dönüşümü ve mikslerin dosya adları çakışabiliyordu; benzersiz kimlik kullanıldı.

## Çalıştırılan kontroller

| Kontrol | Sonuç |
|---|---|
| Python regresyon testleri | 38 geçti |
| Frontend senkron testleri | Geçti: kelime sınırları, erken dolma, JSON dönüşümü, kayıt sırası, hızlı tıklama, ayrı ses örnekleri |
| Ses/video canlı test matrisi | 24 kontrol geçti: 44,1/48 kHz ses dönüşümü, miks, okuma uçları, 8 karaoke tema/oran birleşimi ve 2 görselleştirme videosu |
| Hatalı istek matrisi | 7 kontrol geçti: eksik dosya, yanlış bağlantı, boş metin/düzeltme, geçersiz tempo/tema/görev |
| Gerçek vokal + Large-V3 + Türkçe CTC | Test kopyasındaki seçili satır hizalandı, kaydedildi ve yeniden açıldı; diğer satırlar ve asıl kayıt aynı kaldı |
| Söz kaynağı araması | YouTube bağlantısı Hadise / Ara Beni olarak tanındı, 14 aday bulundu; karşılaştırma 28 satırı korudu |
| Kurulu BS-Roformer-Viperx-1297 | Üretilmiş kısa test sesinin ayrıştırması tamamlandı; yeni model indirilmedi |
| Tarayıcı | Test projesi açıldı; kelime tıklaması 1,751 saniyede durdu; referans arama/yapıştırma/karşılaştırma ve süre uyarısı görüldü; MP4 üretildi; normal ve +12 perde miks önizlemesi çalıştı |
| Video kareleri | İlk kelime başlamadan sarı piksel yok; sessiz arada renk sabit; iki kelime sırasıyla doluyor; 60 fps |
| Arayüz konsolu | Test sırasında hata kaydı görülmedi |
| TypeScript / üretim derlemesi | Geçti |
| ESLint | Komut çalışıyor; 0 hata, 36 uyarı (ayrı iyileştirme gerektirir) |

## Doğrulanamayan veya kapsamı sınırlı kontroller

- JSON indirme butonu denendi; içerik serileştirme testleri geçti. Uygulama içi tarayıcı indirme olayı vermedi ve diske tamamlanmış indirme doğrulanamadı. Bu nedenle gerçek dosya indirme uçtan uca başarılı sayılmadı. JSON/LRC/SRT'nin bütün işletim sistemi indirme pencereleri sınanmış değildir.
- Bütün ayrıştırma modelleri, büyük model indirmeleri, uzun süreli toplu işler, AI restorasyon modelleri ve sistem kapatma/temizleme işlemleri çalıştırılmadı. Mevcut kullanıcı verisini silen işlemler test edilmedi.
- Gerçek şarkının her kelimesi insan tarafından dinlenerek doğrulanmadı. Otomatik hizalamanın tamamlanması, her akustik sınırın kesin doğru olduğu anlamına gelmez. Hece seviyesinde ayrı yeni model eklenmedi.
- Çok uzun şarkılarda bellek/performans yük testi yapılmadı.

Makine çıktıları `tests/.artifacts/feature_smoke.json`, `feature_smoke_48000.json`, `negative_api.json`, `reference_e2e.json`, `separation_smoke.json`, `video_verification.json` ve `eslint.json` dosyalarındadır. Yeniden çalıştırılabilir testler `tests/` klasöründedir.
