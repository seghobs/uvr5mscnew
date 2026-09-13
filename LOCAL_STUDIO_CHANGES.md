# Yerel stüdyo iyileştirmeleri — 12 Eylül 2026

- **Transpoze:** Hedef nota, analiz edilen kaynak ton üzerinden hesaplanır. Kaynak ton elle düzeltilebilir. Ton ve tempo ayrı tutulur; önizleme Rubber Band R3 ile hazırlanır.
- **Projeler:** Kütüphane, kanal ayarları, sözler ve ses parçası bağlantıları `projects/` altında tutulur. Eski tarayıcı kayıtları taşınır. Tamamlanmamış kayıtlar IndexedDB'de bekler ve bağlantı geldiğinde yeniden gönderilir. Dosyalar atomik değiştirilir; bir önceki sürüm korunur. Ses dosyaları `outputs/` içinde kalır; yedek alırken iki klasörü birlikte saklayın.
- **Düzenleme:** Satırlar kilitlenebilir. Kilitli satırlar otomatik düzenlemelerde korunur. Geri al/ileri al geçmişi diske kaydedilir; metin alanı dışında Ctrl+Z, Ctrl+Y ve Ctrl+Shift+Z kullanılabilir. Satır kimlikleri, satır eklenince parça bağlantılarının kaymasını önler.
- **İşler:** Ton önizleme ve transpoze dışa aktarma işleri sıraya alınır; iptal gerçek ses işleme sürecini durdurur. Başarısız veya kesilmiş işler yeniden denenebilir. Eski GPU ayırma işleri de panelde gösterilir; bu işlere yeni iptal mekanizması uygulanmaz.
- **Başlatma:** Sağlıklı ve güncel sunucu tekrar kullanılır. Yeniden başlatma öncesinde kayıtlar tamamlanır; aktif işlem varken yeniden başlatma reddedilir. Yalnız bu proje klasörüne ait süreçler yönetilir. Başlatma işlemleri tek kilitle sıraya alınır.
- **Önbellek:** Ton önizlemeleri en fazla 2 GB / 32 dosya / 7 gün tutulur. Kaynak içerik değişirse eski önizleme kullanılmaz. Temizlik, hazırlanmakta olan dosyalara dokunmaz.

## Doğrulama

- Python: `env/python.exe -m unittest discover -s tests -p "test_*.py"` — 74 test geçti.
- Ön yüz: `tests/` altındaki 9 `.cjs` test dosyası geçti; `frontend` içinde `npm run typecheck` geçti.
- Ses testleri: −12 ile +12 arasındaki 25 yarım ton, tempo bağımsızlığı, süre, frekans, stereo ve geçiş kontrolleri; 24 bit FLAC çıktısı.
- Tarayıcı: Proje yükleme, kaynak tona göre hedef nota, satır kilidi, geri al/ileri al, yenileme sonrası geçmiş ve sunucu yeniden başlatma.
- Dayanıklılık: Bağlantı kesilmesi, 6 MB kayıt, kayıt sürerken yeni düzenleme, açık kimlikle silme, eski kütüphane listesi, iptal ve önbellek doğrulaması.

Tam kapanış, açık kullanıcı oturumunu kapatmamak için gerçek oturumda uygulanmadı; süreç sahipliği ayrı testle doğrulandı. Testler kapsanan senaryoları doğrular; bütün olası seslerde kusursuzluk garantisi vermez.
