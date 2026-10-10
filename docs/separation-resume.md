# Ayrıştırmayı kesintiden sonra sürdürme

Atlas Studio V1/V2 ve tek Roformer ayrıştırmalarında tamamlanan model parçaları
`cache/separation_chunks` içinde atomik olarak kaydedilir. Backend yeniden
açıldığında `cache/separation_tasks.json` içindeki yarım görev aynı kimlikle
yeniden yüklenir. Tamamlanan parçalar tekrar GPU'da hesaplanmaz; mevcut modelin
örtüşme birleştirmesi kayıtlı sonuçlardan yeniden oluşturulur. Diğer modellerde
görev yeniden yüklenir, ancak parça düzeyinde devam desteği yoktur.

Kaynak içeriği, model ağırlıkları, etkili yapılandırma, işleme ayarları,
PyTorch sürümü ve cihaz checkpoint kimliğine dahildir. Her parçanın giriş ve
çıktı özeti kontrol edilir. Bozuk veya farklı kayıtlar yeniden hesaplanır.
Kesinti sırasında henüz atomik olarak kaydedilmemiş parça yeniden hesaplanır.
Geçici arayüz bağlantı kesintisinde durum sorgusu yeniden denenir. Görevleri
iptal etme işlemi, iptal edilmiş görevlerin yeniden açılmasını engeller.

Kayıtlar yerel diskte yer kaplar; bu klasörün silinmesi devam bilgisini siler.
Bu mekanizma bir şarkının ayrıştırma kalitesini veya preset karışımını değiştirmez.

## Doğrulama

- İlk gerçek GPU parçası kaydedildikten sonra backend zorla kapatıldı.
- Backend yeni PID ile açıldı; aynı görev kimliği yeniden yüklendi.
- 16 parçalık işlem tamamlandı. Önceden kaydedilmiş parçanın dosya zamanı
  değişmedi: GPU hesaplaması tekrar yapılmadı.
- İki çıktı da 132300 stereo örnek, 44100 Hz olarak doğrulandı.
- Çökme/yeniden açılma, birebir tensor çıktısı, farklı kaynak, bozuk parça ve
  iptal edilmiş görevin yeniden yüklenmemesi birim testleriyle kontrol edildi.

Canlı test ayrıntıları `cache/separation_resume_check/results.json` içinde,
tekrar çalıştırılabilir kontrol `tools/separation_resume_check.py` içindedir.

## LyricFind erişimi

Canlı kontrolde arama HTTP 200 ve `viewable: true` döndürürken söz API'si HTTP
401 döndürdü. Arama kaydının görünür olması uygulamaya söz API izni vermez.
Arayüz bu sonucu artık etkisiz bir düğme olarak bırakmaz: aynı şarkı ve sanatçı
için diğer kaynaklarda arama yapar. Kaynak erişim kısıtlaması aşılmaz ve farklı
bir şarkının sözleri otomatik uygulanmaz.
