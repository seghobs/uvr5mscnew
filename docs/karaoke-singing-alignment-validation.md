# Otomatik kelime ve hece hizalaması — 31 Ekim 2026

Bu çalışma bir yüzde 100 doğruluk sertifikası değildir.

Sonraki eşlenik deneyde aynı 13 kelimelik sonuç 6'dan 10'a yükseldi.
Aşağıdaki ilk deney tarihsel başlangıç ölçümüdür. Güncel yöntem, diğer
kayıtlar ve Türkçe sınırları için
[kelime sınırı doğrulama raporuna](karaoke-boundary-fix-validation.md) bakın.

## Eklenen yöntem

1. Yerleştirilmiş uygun satırlar, yüksek güvenli kelimeler dahil, iki farklı
   dil uyumlu CTC modeliyle yeniden hizalanır. Uygun orijinal kayıt varsa
   vokal ve orijinal birlikte değerlendirilir. Modellerin tekrar eden aynı
   bağlamları bağımsız oy sayılmaz; çelişen eşit güçlü kümeler seçilmez.
2. Güvenli mevcut zaman ile güçlü model uzlaşması uyuşmuyorsa kelime inceleme
   için işaretlenir. Yüksek güvenli zaman körlemesine değiştirilmez. Zayıf
   zaman ancak komşu kelimeler ve satırlar içinde kalan uzlaşmayla onarılır.
3. İkinci tanıma aşamasının ilk 12 pencere sınırı kaldırıldı. Uygun şüpheli
   pencerelerin tümü, her biri en fazla 35 saniye olacak şekilde incelenir.
   Kurulu Whisper sürümünün desteklemediği Kurmancî açıkça atlanır; yanlış
   `ku` koduyla başarısız denemeler yapılmaz. Kurmancî CTC kontrolleri devam eder.
4. Türkçe hece süreleri karakterlerin ölçülmüş akustik aralıklarından alınır.
   İki farklı modelin uyuşması gerekir; kelime süresi hece sayısına bölünmez.
   Diğer diller için Türkçe hece kuralları uygulanmaz.
5. Hece haritası bağlı olduğu kelime metni ve başlangıç/bitişini taşır.
   Kelime yeniden zamanlanırsa eski harita oynatmada geçersiz olur.
   Yeni CTC çıkarımı eski hece ve doğrulama kanıtlarını devralmaz.
6. Onaylı hece haritası önizlemede, ses parçası düzenleyicisinde ve ASS/MP4
   oluşturucuda kullanılır. İç boşlukta renk ilerlemez; doğrulanmış uzatma
   uç noktası varsa son hece bu uç noktaya kadar sürer.
7. Denetlenemeyen satırlar, eksik modeller ve denetim kapsamı raporda bulunur.
   İşlem ilerlemesinin tamamlanması akustik doğruluk olarak gösterilmez.

## Gerçek kayıt deneyi

`karaoke-phrase-audit-validation.json`: kullanıcının üç Türkçe kaydından
toplam dokuz satır, kayıtlar değiştirilmeden incelendi. 29 kelimede model
uzlaşması bulundu; dört yüksek güvenli kelimede sınır uyuşmazlığı işaretlendi;
15 hece önerisi uzlaşmayla üretildi. İnsan referansı bulunmadığından bunlar
doğru/yanlış oranı değildir. İşaretlenen dört kelimenin yanlışlığı kanıtlanmadı.

`karaoke-jamendo-benchmark.json`: JamendoLyrics'in ilk İngilizce kaydındaki
ilk üç satırın 13 kelimesiyle bağımsız referans deneyi yapıldı. Satır
pencereleri referanstan verildi; dolayısıyla bu tüm şarkı otomasyon testi
değildir. Kelimelerin tümü yerleştirildi, fakat hem başlangıç hem bitişin
80 ms tolerans içinde olması ölçütünde 6/13 kelime başarılıydı. Başlangıç
ortalama mutlak hatası yaklaşık 72 ms, bitiş hatası 89 ms idi. Ek denetim
bu örnekte zamanları değiştirmedi; ölçülmüş bir doğruluk artışı iddiası yoktur.
Bu sonuç, yüzde 100 doğruluk iddiasında bulunmamamız gerektiğini gösterir.

Yeni değerlendirme aracı: `tools/evaluate_lyric_alignment.py`.
Referans türü, aynı ses kaydını doğrulayan SHA-256, eksik/yanlış/fazla
kelimeler, başlangıç/bitiş MAE ve sınır p95 raporlanır. Model uzlaşması
insan doğrulaması olarak kabul edilmez. Tekrarlanan sözler satır kimliği ve
kelime konumuyla ayrı değerlendirilir.

## Kaynaklar

- [ISMIR 2025, kaynak ayrıştırma koşullarında hizalama](https://ismir2025program.ismir.net/lbd_412.html):
  ayrıştırma yöntemi ve vokal kalitesi sonuçları etkiler. Tek bir ayrılmış
  kanalı hatasız referans saymama kararı bu nedenle korunmuştur.
- [Şarkıya uyarlanmış akustik modeller, Interspeech 2019](https://www.isca-archive.org/interspeech_2019/gupta19b_interspeech.html):
  şarkı akustiği konuşmadan farklıdır. Burada bu makalenin modelini yeniden
  eğittiğimiz veya Türkçe başarımını kanıtladığımız iddia edilmez.
- [JamendoLyrics veri ve açıklamaları](https://huggingface.co/datasets/jamendolyrics/jamendolyrics):
  bağımsız kelime zamanlama değerlendirmesi için kullanıldı. Kaynak ses ve
  tam sözler uygulama deposuna eklenmedi; yalnızca sayısal ölçümler kaydedildi.

Kapsam sınırları: 18 saniyeden uzun veya henüz yerleştirilmemiş satırlar bu
ek yerel denetimde atlanır; ana hizalama ve mevcut kurtarma aşamaları çalışmaya
devam eder. Birbirine karışan vokal, yanlış söz sürümü, alışılmadık telaffuz ve
vokal ayırma kayıpları hâlâ belirsizlik oluşturabilir. Hiçbir kaynak veya test
bütün şarkılarda sıfır hatayı kanıtlamamaktadır.
