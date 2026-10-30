# Kurmancî şarkıda sonucun reddedilmesi

Sonraki çalışmada kalan eksik kelime ve 33 uyarı da incelendi; revizyon 5
kaydedildi. Güncel sonuç ve kanıtlar:
[şarkı tamamlama raporu](karaoke-war-song-completion.md).
Bu dosyanın aşağıdaki sonuçları önceki revizyon 4'ü anlatır.

31 Ekim 2026. Etkilenen kayıt: `AtlasStudio_Vocals_0e450a0a9820.wav`.

Kayıt 16 sıfırlanmış söz satırı içeriyordu. Eski hazırlık, tek başına da
bulunan nakaratı virgüllü satırdan ayırarak 18 satır oluşturuyordu. Eklenen
tekrarların `repeat_source_id` alanı bu yeni iç satırlara işaret edebiliyor;
arayüz bu kimlikleri özgün editör görüntüsünde bulamıyordu. Böylece
`Tekrar satırı doğrulanamadı` hatasıyla bütün sonuç reddediliyordu.
Ayrıca kaynak satırın metni değiştiği için satır sırası/metin kontrolü de
bu çıktıyla uyumsuzdu.

Genel hizalama girişinde söz satırlarını bölme kapatıldı. Sözler, kimlikler,
elle onaylanmış zamanlar ve arayüzün sonuç doğrulaması korunur. Ayrı deneysel
cümle arama yardımcısı açıkça istendiğinde kullanılabilir; editöre uygulanacak
sonuç artık bu yardımcı tarafından bölünmez. Bunun bedeli, aralıklı söylenen
bazı birleşik ifadelerin ek dinleme kontrolü gerektirebilmesidir.

Gerçek kayıt hazırlığı kontrolü: 16 → 16; bütün kaynak kimlik/metin çiftleri
eşit. 485 Python testi ve mevcut frontend sonuç doğrulama testi başarılı.
Bu düzeltme sonucun uygulanmasını engelleyen yazılım hatasını giderir;
akustik zamanlamanın insan tarafından doğrulandığı anlamına gelmez.

## Gerçek şarkıda yeniden çalıştırma

Yeni sonuç arayüzdeki `validateSuppliedResult` kontrolünden geçti ve
revizyon 3 değişmemişken karşılaştırmalı kaydetmeyle revizyon 4 olarak
kaydedildi. Özgün 16 satırın bütün metin ve kimlikleri korundu; otomatik
tekrarlar ve müzik etiketleriyle toplam 46 satır oluştu. 98 kelimenin 97'si
zaman aralığına sahip; 1 kelime hâlâ eksik. Eksik kelimenin yerel Kurmancî,
Türkçe CV7 ve CV8 denemeleri yeterli güven üretmedi; zorla onaylanmadı.
Altı saniyeden uzun dört otomatik kelime ayrıca dinleme kontrolüne işaretlendi.
Toplam 33 editör uyarısı (eksik kelime dahil) kalıyor. ASS oluşturmayı
engelleyen yapısal zamanlama hatası yok; bu, işitsel doğruluk onayı değildir.
Sayısal kayıt: [doğrulama özeti](karaoke-war-song-validation.json).
