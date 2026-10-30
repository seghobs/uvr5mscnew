# Kalıcı otomatik hizalama onarımı

31 Ekim 2026. Yeni kontroller, normal **Otomatik senkronla ve bağla** akışında
çalışır. Şarkı adı, dosya kimliği veya belirli saniyeler algoritmaya yazılmadı.
Önceki şarkıya özel araştırma araçlarının kelime, ifade ve DTW kontrolleri
`karaoke_automatic_recovery.py` içinde genel bir aşamaya taşındı.

## Otomatik davranış

1. Nakarat parçaları içeride ayrı bulunur, özgün satır kimliği ve sözler
   korunarak yeniden birleştirilir. Dalga biçimiyle bulunan zayıf bir ön parça
   da ifadenin devamıyla tekrar eşleştirilir. Daha uzun nakaratların içindeki
   ölçülmüş kısa nakaratlar karşılaştırma kaynağı olabilir.
2. Şüpheli, eksik veya yalnızca tahmin edilmiş kelimeler kurulu uygun modeller,
   farklı bağlamlar ve ses kanallarıyla yeniden denenir. Aynı modelin bağlamları
   ayrı model oyu sayılmaz. Eşit destekli farklı yerleşimler otomatik seçilmez.
3. Güvenilir ölçülmüş tekrarlar, hem aynı sözcük hem farklı sözcük örnekleriyle
   karşılaştırılır. Yalnızca benzer ses bulmak yetmez: pozitif/negatif ayrımı,
   CTC sınır desteği ve yeni aralığın yeniden akustik kontrolü gerekir.
4. Kalan uygun kelimelerde bütün ifade karşılaştırılır. Süreyi ve sessizlikleri
   koruyan DTW aktarımında tutarlı tekrar kümesi kullanılır; en yakın iki sesin
   çelişkili sınırları körlemesine ortalanmaz. Kelime komşularının dışına çıkılmaz.
5. Kaynaklar aşamalı olarak dondurulur. Tahmini süreler akustik kanıt olarak
   kullanılamaz; bir ifade onarımı başka bir ifade onarımının kaynağı olmaz.
6. Virgülden sonra boşluk bulunmayan editör kelimesi model girdisinde parçalara
   ayrılır. Özgün yazım korunur; ölçülmüş alt aralıklar `timing_parts` ve bağlı
   kelime görüntüsüyle saklanır. Önizleme, ses parçaları ve ASS/MP4 aynı aralıkları
   kullanır. İç nefes boşluğunda renk ilerlemez. Eski kelime/metin/zaman görüntüsü
   değişirse bu harita geçersiz olur. Bu parçalar dilbilimsel hece sayılmaz.
7. Enerji kuyruğu tek başına kelimeyi uzatamaz. Onaylı mevcut model sınırıyla
   çelişen kanıtsız yankı, sözcüğü yeniden yanlış diye işaretleyemez; önceden
   bulunan başka uyarı da silinmez.
8. Otomatik müzik etiketleri son kelime onarımlarından sonra yerleştirilir.
   Böylece erken çizilmiş bir SOLO etiketi gerçek uzatmanın önünü kesmez.

## Orijinal ses ve kayıt koruması

Eski ayrıştırmalarda kaynak bağlantısı yoksa `uploads` ve `ytdl` içindeki
uygun dosyalar incelenir. Dosya adı kullanılmaz: kanal, örnekleme hızı ve örnek
sayısı aynı olmalı, önce farklı bölgeler, sonra **bütün ses** vokal/enstrümantal
toplamıyla PCM yuvarlama toleransı içinde eşleşmelidir. Uzun kaydın ortalamasında
saklanabilecek yerel bir değişiklik için ayrıca örnek başına hata sınırı vardır.
Farklı sürüm veya zaman kayması bu yolla kaynak kabul edilmez.

Elle bağlanmış kelimeler, tamamen elle doğrulanmış satırların ek boşlukları ve
kilitli satırlar korunur. Denemeler kopyada yapılır; yeni çakışma veya aşama
hatasında önceki sonuç korunur. İptal, model denemelerinin satır ilerlemelerinde
işlenir. Kurulu olmayan ek modeller için indirme başlatılmaz. Son ek kontrol,
yardımcı dil geçişinde ikinci kez çalıştırılmaz.

Kayıt revizyonu denetimi devam eder: eski editör görüntüsü kaydedilemez.
Mevcut şarkılar yalnızca açıldıkları için yeniden zamanlanmaz; yeni kontrol
hizalama başlatıldığında çalışır.

## Ölçülen kontroller

- Dil Disoje'nin **ham otomatik yerleşimleri**, elle hazırlanmış son zamanlar
  verilmeden yeni genel aşamadan geçirildi. 36 editör uyarısı ve 3 ek noktalama
  parçası hedefi vardı. 28 model uzlaşması, 9 sözcük tekrarı ve 2 ifade/DTW
  onarımı sonrası eksik kelime, editör uyarısı ve yapısal hata kalmadı.
  Test mevcut kaydı değiştirmedi. Özgün metinle 99 editör tokenı ve 3 ölçülmüş
  noktalama içi harita vardır; önceki elle boşluk eklenmiş 102 tokenla payda aynı değildir.
- İki başka gerçek kayıtta üçer mevcut makine kelimesine kontrollü 40 ms
  kaydırma ve inceleme işareti uygulandı. Seçilen altı kelime yeniden zamanlandı,
  uyarıları çözüldü; kayıtlı sürümlere yazılmadı. Bu, insan doğruluğu ölçümü değildir.
- Bilinen çalgısal bölümlere yerleştirilen **4 yanlış kelimenin hiçbiri onaylanmadı**.
- Önceki sabit 13 kelimelik insan referansında, aynı cümle pencereleri ve 80 ms
  başlangıç/bitiş toleransıyla sonuç 10/13 → 10/13 kaldı. İyileşme uydurulmadı;
  bu küçük kontrol yalnızca söz konusu örnekte gerileme olmadığını gösterir.
- 516 Python testi, 20 frontend test dosyası ve TypeScript kontrolü başarılı.
  Canlı API eski revizyonu 409, geçersiz iç zaman aralığını 422 ile reddetti;
  aktif şarkı ve LRC/SRT çıktıları değişmedi. Güncel üretim derlemesi çalışıyor.

Bu yöntem **akustik/model doğrulamasıdır**. Uyarının kalmaması insan dinlemesiyle
ölçülmüş yüzde 100 doğruluk değildir. Yetersiz veya çelişkili kanıtta uyarı
korunur. Yerel hizalama pencereleri ve akustik karşılaştırma bütçesi aşıldığında
bu durum rapora yazılır; test edilmemiş adaylar onaylanmaz.

[Gerçek kayıt kontrolleri](karaoke-permanent-recovery-validation.json),
[insan referanslı küçük regresyon kontrolü](karaoke-permanent-recovery-human-benchmark.json),
[canlı kayıt koruma kontrolleri](karaoke-permanent-recovery-live-checks.json).
