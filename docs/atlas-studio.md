# Atlas Studio

19 Eylül 2026 · Yerel vokal / enstrüman preseti

## Algoritma incelemesi

[MVSEP algoritmalar sayfasının](https://mvsep.com/tr/algorithms) bütün bölümleri incelendi. Aşağıdaki gruplama, bu uygulamadaki iki kanal hedefine göre değerlendirmemizdir; bütün modelleri yerelde çalıştırdığımız anlamına gelmez.

| İncelenen aileler | Bu preset için değerlendirme |
| --- | --- |
| İki kanallı Ensemble; BS Roformer, 124 bands, fullness duality; BSPolarFormer; MelBand Roformer; SCNet; MDX23C; MDX-B; UVR; Demucs4 Vocals | Vokal / enstrüman hedefiyle ilgili. SDR, dolgunluk ve sızıntı birlikte değerlendirilmeli. |
| Çok kanallı Ensemble, All-In, BS Roformer SW, Demucs4 HT | Daha fazla enstrüman kanalı gereken işler için. |
| Karaoke ve MDX-B Karaoke | Ana vokal / geri vokal ayrımı farklı bir hedef. |
| Crowd removal, Medley Vox, Multichannel BS, Male/Female, Choir, SATB | Özel kaynak veya kanal yapısı gerektiren işler. |
| Drums, Bass, Synth, DrumSep, Piano, Keys, Organ, Rhodes | Tek enstrüman odaklı; hepsini peş peşe uygulamak iki kanal için doğru strateji değil. |

Tablolarda dolgunluk ile sızıntı arasında ödünleşim var. Sıfır sızıntı ve kusursuz kaynak ataması garanti edilemez. MVSEP’in özel ağırlıkları yerel model dosyalarıyla özdeş kabul edilmedi.

Mevcut katalogdaki “124 bands 2026.07” girdisi [pcunwa/BS-Roformer-Leap](https://huggingface.co/pcunwa/BS-Roformer-Leap) dosyasına yöneliyor. MVSEP sürümüyle özdeşliği doğrulanamadığı için Atlas seçimine veya puan iddiasına dayanak yapılmadı.

## Yerel uygulama

Hazır Akıllı Stüdyo Presetleri → **Atlas Studio → Uygula**. Ardından ayırmayı başlatın. Önceki presetler korunur. Modeller uygulamanın mevcut indirme mekanizmasıyla yüklenir; ses dış hizmete gönderilmez.

| Model | Rol | Katkı |
| --- | --- | --- |
| BS-Roformer-Viperx-1297 | Temel vokal tahmini | %50 |
| MelBand Kim FT2 Bleedless / unwa | Vokal uzmanı | %25 |
| MelBand Kim Inst V2 / unwa | Kaynaktan enstrüman çıkarılarak elde edilen vokal tahmini | %25 |

Bu ağırlıklar tutucu bir tasarım seçimidir; bir doğrulama veri kümesinde optimize edilmiş veya dünyadaki en iyi sonuç olduğu kanıtlanmış katsayılar değildir.

Üç vokal tahmini birleştirilir; enstrüman, kaynak eksi birleşik vokal olarak hesaplanır. Böylece iki kanalın toplamı, sayısal hassasiyet sınırında, hazırlanmış kaydı verir. **Bu kontrol, seslerin doğru kanala atandığını kanıtlamaz.** Genel ilke: [mixture consistency çalışması](https://arxiv.org/abs/1811.08521).

- Her modelin kendi pencere süresi korunur. %87,5 örtüşme, pencerenin sekizde biri ilerleme olarak uygulanır. Kurulu audio-separator 0.32 Roformer yolunun saniye birimine özel dönüşüm yapılır.
- İşlemler sırayla çalışır; GPU belleği modeller arasında temizlenir.
- Ara sesler ve varsayılan WAV çıktılar 32-bit float kullanır. WAV tepe değerleri kırpılmaz. Kaynak, modellerin ortak zaman tabanı olan stereo 44,1 kHz’e hazırlanır; bu, farklı örnekleme hızındaki kaynakla bit düzeyinde özdeşlik değildir.
- FLAC seçilirse 24-bit yazılır. Taşma durumunda iki kanala aynı kazanç uygulanır ve işlem mesajında miktarı belirtilir.
- Konuşma algılamasıyla susturma, solo bölümlerini değiştirme, gürültü kapısı veya agresif sonradan temizleme yoktur.
- Eksik model çıktısı, farklı süre/kanal yapısı, geçersiz sayısal değer veya tepe normalizasyonu algılanırsa işlem başarısız olur; başka modele sessizce geçilmez. Geçici dosyalar temizlenir.

## Doğrulama

Ezo kaydının 80–100. saniyeleri üç gerçek modelle RTX 5060 üzerinde işlendi: yaklaşık 46 saniye. Çıktılar stereo 44,1 kHz ve tam 882.000 örnektir. İki kanal toplamının kaynağa en büyük örnek farkı `2.98e-8` oldu. Bu ölçüm sızıntı puanı değildir; bu kaydın gerçek izole stüdyo kanalları bulunmadığından SDR/sızıntı iyileşmesi ölçülmedi.

Otomatik kontroller: profil yönlendirmesi, model listesi, WAV/FLAC doğrulaması, farklı model pencere sürelerinde örtüşme, örnek sayısı, stereo koruması, toplam sinyal, geçersiz çıktılar ve hata sonrası temizlik. Yeni preset, önceki preset ve eksik model durumları arayüz testinde kapsanır.
