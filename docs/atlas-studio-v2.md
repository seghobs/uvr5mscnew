# Atlas Studio V2 — müzik bütünlüğü öncelikli

Güncel sürüm: `three-model-smooth-music-v2`. Enstrüman, davul ve basın doğal kalması önceliklidir. V1 değiştirilmedi.

Aynı üç model korunur: Viperx 1297, Kim FT2 Bleedless, Kim Inst V2. Her model bir kez çalışır; üç model ve üç çıkarım vardır. Çıktılar frekansla yumuşak değişen, negatif olmayan ve her frekansta toplamı bir olan ağırlıklarla birleştirilir. Yeni model, ikinci vokal temizleme geçişi, frekans susturma veya enstrümana kapı eklenmez. İlk ayrım modelleri hâlâ müziği vokal sanabilir ve vokal sızıntısı bırakabilir. Frekansa göre model seçimi bu riski sıfırlamaz.

0, 80, 250, 1000, 4000, 10000 ve 22050 Hz düğümlerindeki karışım sekiz geliştirme kesitinde ayarlandı. Geliştirme ortalamasında koşullu artefakt artık enerjisi ve vokal izdüşüm gücü önceki V2'yi aşamaz. Düğümler arası değişim düzenlileştirilir; frekanslar arasında doğrusal geçiş vardır. Çıkarım fazı veya kanallar bağımsız normalleştirilmez. Uzun sesler, aynı STFT sonucunu koruyan hizalı ve örtüşen bloklarla birleştirilir; bu sadece geçici bellek kullanımını sınırlar.

Sekiz değerlendirme kesitinde ortalama enstrüman SDR'si V1 18,275; önceki V2 18,356; aday 18,409 dB. Bas/gövde/atak bant hata ve atak ölçümleri, spektral eksilme/fazlalık, vokal izdüşümü ve koşullu artefakt artığı ortalamaları önceki V2'den düşük. Orijinal davul ve bas referanslarına koşullu doğrusal kazanç hatası da ortalamada düşük. Bunlar kısa ve daha önce tekrar kullanılmış yerel kesitlerdir; yeni ve bağımsız bir genel kalite testi değildir. Ortalama kazanımlar her şarkı veya bölümde iyileşme kanıtlamaz. Daha agresif serbest karışım ve dört uzlaşma yöntemi artefakt/müzik koruma nedenleriyle elendi.

Ezo'nun aynı üç orijinal model tahmininden 305,18 saniyelik Ezo_V2_Refined_Instrumental.wav üretildi. Önceki karşılaştırmanın sabit 39 düşük-vokalli saniyesinde bas/gövde/atak spektral eksilme ve atak hatası önceki V2'den düşük. Bu bölgeler Viper modeli tarafından seçildi; izole müzik değildir. Tam kayıt Viper artık-vokal tahmini V1 -54,72; önceki V2 -55,76; aday -57,15 dBFS. Bu, aynı toplulukta bulunan bir modelin yanlı tahminidir, gerçek vokal sızıntı ölçümü değildir. Üç sözlü kesitte ASR kaynak söz eşleşmesi yok; bu da sıfır vokal kanıtı değildir. Çıktı tepe değeri 0,92651; kırpma yok ve süre/stereo korunur. 23 sayısal kabul kontrolü geçti.

İzole referans kanalları olmadan gerçek SDR, sıfır müzik kaybı ve sıfır sızıntı doğrulanamaz. Kaynak toplamı kontrolü doğru kaynak ayrımı kanıtı değildir. Önceki atlas-studio-v2-ezo-check.json tarihsel dört geçişli sürüme aittir; oradaki 22,6 dB model tahmini azalması bu sürüme aktarılmaz.

Güncel rapor: [atlas-studio-v2-refined-check.json](atlas-studio-v2-refined-check.json). Yeni sesler outputs/Ezo_Music_Refined klasöründe: Ezo_V2_Refined_Instrumental.wav ve Ezo_V2_Refined_140_156.wav. Önceki music-check ve ezo-check raporları tarihsel sürümlere aittir. Dinleme testi yapılmadı; belirgin işitsel üstünlük veya sıfır kayıp iddia edilmez.

Varsayılan WAV stereo 44,1 kHz float; örtüşme %87,5. FLAC tepe taşmasında iki kanala ortak seviye azaltılması uygulayabilir. V2 → Uygula yeni tarifi seçer; başlamış işler değiştirilmez.
