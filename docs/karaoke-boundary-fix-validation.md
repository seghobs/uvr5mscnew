# Kelime sınırları: eşlenik deney ve güvenlik düzeltmeleri

31 Ekim 2026. Bu sonuçlar bütün şarkılar için doğruluk garantisi değildir.

## Aynı testte ölçülen değişim

İnsan etiketleri, ses dosyası ve 80 ms tolerans değişmedi. Bir kelimenin
başlangıcı **ve** bitişi tolerans içinde olmalı. Referans cümle pencereleri
kullanıldı; bu, baştan sona otomatik şarkı hazırlama testi değildir.

| Kayıt / bölüm | Kelime | Önce: İngilizce MMS | Sonra: İngilizce LV60 + sınır düzeltmesi |
| --- | ---: | ---: | ---: |
| HILA / aynı hedef | 13 | 6 | 10 |
| HILA / sonraki satırlar | 75 | 28 | 42 |
| Quentin Hannappe / diğer kayıt | 99 | 52 | 65 |
| Songwriterz / diğer kayıt | 93 | 32 | 40 |
| Toplam | 280 | 118 | 157 |

Hedef 13 kelimede başlangıç ortalama mutlak hatası 72 ms'den 35 ms'ye,
bitiş hatası 89 ms'den 60 ms'ye indi. Üç kelime hâlâ ölçütü karşılamıyor.
Sadece sınır politikasını değiştirmenin etkisi de her iki model için ayrı
ölçüldü: [ham sonuçlar](karaoke-boundary-fix-benchmark.json).

## Uygulanan değişiklikler

- CTC karakter emisyonlarının kısa boşluklarında sınırlı sınır düzeltmesi.
  Başlangıç en fazla 80 ms, bitiş en fazla 160 ms genişler; uzun nefesler
  dağıtılmaz. Güven puanı yükseltilmez. Otomatik politika İngilizceyle sınırlı.
- İngilizce ana hizalayıcı LV60; MMS karşılaştırma kanalı olarak korunur.
  Elle zamanlanmış kelime içeren ilk hizalamada sınır genişletmesi uygulanmaz.
- Enerjiye dayalı vokal uzatma artık yalnız başına zaman değiştiremez.
  Aynı kelimenin uç noktasını iki farklı model desteklemelidir. Yankı adayı
  desteklenmezse mevcut zaman korunur ve dinleme kontrolü istenir.
- Whisper sözcük zamanları tek başına fonetik zamanların üzerine yazılmaz.
  Tanıma çıktısı sözcük kanıtıdır; zaman onarımı CTC uzlaşması gerektirir.

## Türkçe ve reddedilen deneyler

Üç farklı icracının insan zamanlamalı Türk makamı kayıtlarında 16 kelime
ayrıca ölçüldü: [sonuçlar](karaoke-turkish-boundary-benchmark.json).
Türkçe CV7 temelinde 3/16, aynı kısa sınır düzeltmesiyle 4/16 sağlandı.
Uzun melismaların bitişleri büyük hata kaynağı olmaya devam ediyor.
Bu nedenle İngilizcedeki kazanım Türkçeye genel başarı gibi sunulmadı;
Türkçe için yeni sınır politikası otomatik açılmadı.

İki vokal ayırıcı, şarkıya özel yayımlanmış hizalayıcı, CTC boşluk cezası,
voicing önceliği ve daha geniş bağlam denendi. Bazıları hedef örneği
iyileştirirken diğer kayıtları bozdu; genel yöntem olarak etkinleştirilmedi.
Stereo enerji kuyruğunun yankıyla yaklaşık 1,5 saniye hatalı uzayabildiği
gözlendi; yeni iki-model uç nokta koşulu bu hata sınıfını engeller.

## Kaynaklar ve kapsam

Tekrar çalıştırılabilir İngilizce karşılaştırma:
`env/python.exe tools/benchmark_karaoke_boundaries.py --metadata .runtime/jamendo-three-metadata.json --audio-dir .runtime/jamendo-benchmark --output .runtime/repeated-boundary-benchmark.json`.
Metadata JamendoLyrics'in ilgili üç kayıt için `name`, `file_name`, `lines`
ve `words` alanlarını içerir; telifli tam sözler bu depoya eklenmemiştir.

Regresyon doğrulaması: 484 Python testi, 20 frontend test dosyası ve
TypeScript tür kontrolü başarılı.

- [JamendoLyrics veri kümesi](https://huggingface.co/datasets/jamendolyrics/jamendolyrics)
- [Türkçe elle zamanlanmış makam kayıtları](https://zenodo.org/records/1287656)
- [Çok dilli şarkı hizalama araştırmasının kaynak kodu](https://github.com/jhuang448/LyricsAlignment-Multilingual)

Araştırma sesleri ve tam sözleri dağıtılmadı. Test raporları sayısal
ölçümleri ve kayıt kimliklerini içerir. Eski kayıtları koruma kontrolünde
canlı API eski revizyonu 409, revizyonsuz yazmayı 428 ve NaN zamanı 422
ile reddetti; 52 satırın içeriği, revizyonu ve altyazı dosyaları değişmedi.
