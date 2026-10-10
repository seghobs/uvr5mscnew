# Şarkı sözü kaynakları

Bu paket, kullanıcının `Desktop/lyric` projesindeki `providers.py` ve LyricsTranslate ayrıştırıcısından uyarlanmıştır. Asıl proje değiştirilmez; uygulama bu klasörün başka bir bilgisayarda bulunmasına ihtiyaç duymaz.

UVR'nin mevcut sunucusu `/api/lyrics/catalog/search` ve `/api/lyrics/catalog/lyrics` adreslerini sunar. Ayrı sunucu, port veya başlatma betiği yoktur. Arama ve söz getirme kayıtları değiştirmez; kullanıcı seçtiği metni inceleyip mevcut senkronlama akışını başlatır.

- LyricsTranslate: orijinal söz bölümü; çeviriler alınmaz.
- LRCLIB: düz metin sözler. Kaynak zamanları farklı kayda ait olabileceği için otomatik uygulanmaz.
- Genius: halka açık arama ve söz bölümü.
- LyricFind: arama sonuçları; söz API erişimi kısıtlıysa sonuç tıklanarak aynı şarkı ve sanatçı diğer kaynaklarda aranır. `viewable` alanı söz API'si izni anlamına gelmez.
- Musixmatch: API anahtarı olmadan, sanatçı ve şarkı adından halka açık şarkı sayfası bulunur. Sözler HTML içindeki `__NEXT_DATA__` JSON verisinden alınır. Kaynak engelleri veya CAPTCHA aşılmaz; sayfa yapısı değişirse kaynak hatası gösterilir.

Her arama kaynağı en fazla 22 saniye beklenir, söz getirme toplam 25 saniyeyle sınırlıdır. Hatalar kaynak bazında gösterilir; kullanıcı her zaman elle söz yapıştırabilir. Dış kaynakların HTML veya erişim kurallarındaki değişiklikler ayrıştırıcı güncellemesi gerektirebilir. Anahtarlar yanıtlara eklenmez. Sözlerdeki satırlar ve kıta boşlukları korunur.

Bağımlılıklar ana `requirements.txt` üzerinden `setup.bat` ile kurulur. Kontroller: `env/python.exe -m unittest discover -s tests -p test_lyrics_catalog.py`.

Musixmatch araması 10 Ekim 2026 tarihinde gerçek tarayıcı araması ve ağ trafiğiyle incelendi. `/search?query=...` ekranı, dağıtıma bağlı `/_next/data/<buildId>/en/search.json?query=...` yanıtını kullanıyor; yakalanan HTTP 200 yanıtında `data.openSearch.error = __COM_RESPONSE_408__` vardı, şarkı sonuçları yoktu. Sonraki arama giriş ekranına yönlendirildi. Arama JavaScript'i ayrıca `community/opensearch/tracks` yolunu tanımlıyor; doğrudan anonim istekte bu yol geçerli sonuç sağlamadı. Bu uçlar çalışan, anahtarsız arama API'si olarak kullanılmıyor ve dağıtım kimliği sabitlenmiyor. Erişilebilir şarkı sayfasındaki JSON yöntemi ayrı olarak çalışır. Sanatçı boş bırakıldığında diğer kaynaklardaki tam başlık eşleşmesinden sanatçı bulunarak bu sayfa denenir.
