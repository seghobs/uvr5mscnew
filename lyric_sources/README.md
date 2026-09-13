# Şarkı sözü kaynakları

Bu paket, kullanıcının `Desktop/lyric` projesindeki `providers.py` ve LyricsTranslate ayrıştırıcısından uyarlanmıştır. Asıl proje değiştirilmez; uygulama bu klasörün başka bir bilgisayarda bulunmasına ihtiyaç duymaz.

UVR'nin mevcut sunucusu `/api/lyrics/catalog/search` ve `/api/lyrics/catalog/lyrics` adreslerini sunar. Ayrı sunucu, port veya başlatma betiği yoktur. Arama ve söz getirme kayıtları değiştirmez; kullanıcı seçtiği metni inceleyip mevcut senkronlama akışını başlatır.

- LyricsTranslate: orijinal söz bölümü; çeviriler alınmaz.
- LRCLIB: düz metin sözler. Kaynak zamanları farklı kayda ait olabileceği için otomatik uygulanmaz.
- Genius: halka açık arama ve söz bölümü.
- LyricFind: arama sonuçları; söz erişiminin yetki gerektirdiği gösterilir.
- Musixmatch: `MUSIXMATCH_API_KEY` ortam değişkeni varsa resmi API kullanılır. Erişim ve dönen sözlerin kapsamı hesaba bağlıdır.

Her arama kaynağı en fazla 22 saniye beklenir, söz getirme toplam 25 saniyeyle sınırlıdır. Hatalar kaynak bazında gösterilir; kullanıcı her zaman elle söz yapıştırabilir. Dış kaynakların HTML veya erişim kurallarındaki değişiklikler ayrıştırıcı güncellemesi gerektirebilir. Anahtarlar yanıtlara eklenmez. Sözlerdeki satırlar ve kıta boşlukları korunur.

Bağımlılıklar ana `requirements.txt` üzerinden `setup.bat` ile kurulur. Kontroller: `env/python.exe -m unittest discover -s tests -p test_lyrics_catalog.py`.
