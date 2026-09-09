# Sözleri bul ve doğrula

Karaoke stüdyosuna “Sözleri bul ve doğrula” eklendi. Whisper yeniden söz çıkardıktan sonra bu pencere açılır. İlk kullanımda YouTube bağlantısı veya sanatçı/şarkı adı girilir; başarılı arama bilgisi bu dosya için tarayıcıda hatırlanır. Sonraki açılışta yeniden arama ve karşılaştırma başlar.

YouTube oEmbed başlıktan şarkıyı belirler. LRCLIB ücretsiz API'si referans adaylarını getirir. Adaylar ses süresine yakınlığa göre sıralanır; ilk adayın karşılaştırması otomatik gösterilir. Bu bir sürüm doğruluğu garantisi değildir. Resmî kaynakların genel amaçlı otomatik taraması eklenmedi; resmî metin elle yapıştırılabilir. Ses dosyası dış servise gönderilmez.

Karşılaştırma mevcut kayıt satırlarını korur. Tekrarlanan nakaratlar silinmez, internetteki fazladan kıtalar eklenmez, eşleşmeyen satırlar değiştirilmez. Öneriler kelime metni benzerliğine dayanır; akustik doğrulama veya kesin doğru söz etiketi değildir. Kullanıcı uygulanacak satırları seçer ve öneriyi düzenleyebilir.

Seçilen satırlar komşu satırların sınırları içinde vokalden kesilerek mevcut Whisper/stable-ts ve Türkçe CTC hizalamasından geçer. Diğer satırlar aynı zaman ve kelime verileriyle kalır. Sonuçlarda kelime kaybı, çakışma, ses penceresini aşma veya bu sırada yapılmış başka bir düzenleme varsa kayıt yapılmaz. Başarılı değişiklikler mevcut SQLite geçmişi üzerinden kaydedilir. Düşük güvenli akustik sonuçlar uyarı olarak kalabilir.

Hece seviyesinde yeni bir akustik model bu değişikliğin kapsamında değildir; bu aşama metin doğrulaması ve kelime zamanlaması temelini kurar. Doğru söz metni tek başına milisaniyelik akustik sınır garantisi vermez.

Doğrulama: 36 Python testi; mevcut frontend senkron testleri; Next.js üretim derlemesi. Gerçek YouTube bağlantısı Hadise / Ara Beni olarak tanındı, LRCLIB adayları döndü. Canlı salt-okunur karşılaştırma kontrolü `tests/check_reference_live.py` ile yapılır. Kullanıcının şarkı sözleri bu geliştirme sırasında otomatik değiştirilmez.

Kaynak: https://lrclib.net/docs
