# UVR5 Next Studio

Yerel bilgisayarda çalışan Next.js ses stüdyosu. Arayüz Next.js/React, ses işleme sunucusu FastAPI/Python kullanır.

## Başlatma

Proje klasöründeki `start.bat` dosyasını açın. Başlatıcı `frontend` uygulamasını ve `env/python.exe` üzerinden Python sunucusunu çalıştırır.

- Arayüz: http://localhost:3000
- API: http://localhost:8000
- Sunucu günlüğü: `logs/backend.log`

Bu kurulu çalışma kopyası `env/` ve `frontend/node_modules/` bağımlılıklarını kullanır. Bu klasörler uygulamanın çalışması için gereklidir.

## Proje yapısı

- `frontend/`: Next.js arayüzü ve ön yüz bağımlılıkları.
- `api_modern.py`, `service_control.py`: API ve başlatma/yeniden başlatma yönetimi.
- `core.py`, `studio_pro.py`, `audio_*.py`, `karaoke_*.py`: ses ayırma, transpoze ve karaoke işlemleri.
- `local_projects.py`, `projects/`: kalıcı proje kayıtları.
- `assets/`: ortak yapılandırma, model listesi ve aktif veritabanı.
- `models/`, `tools/`, `env/`: modeller, ses işleme araçları ve Python ortamı.
- `outputs/`, `uploads/`, `ytdl/`: çalışmalar ve ses dosyaları.
- `cache/`, `logs/`, `.runtime/`: önbellek, günlükler ve servis çalışma bilgileri.
- `tests/`: doğrulama ve hata tekrarlama testleri.

Eski Gradio ve HTML arayüzleri ile kök klasördeki alternatif npm başlatıcısı kullanılmaz. Tek başlatıcı `start.bat` dosyasıdır.

## Testler

Proje kökünde:

```powershell
.\env\python.exe -m unittest discover -s tests -p 'test_*.py'
Get-ChildItem tests -Filter *.cjs | ForEach-Object { node $_.FullName }
```

`frontend` klasöründe: `npm run typecheck`.

## Kayıtlar ve yedekleme

Çalışmaları yedeklerken `projects/`, `assets/favorites.db` ve ilgili `outputs/` ses dosyalarını birlikte saklayın. Uygulamanın genel ayarlardaki toplu temizlik işlemi çalışma dosyalarını siler.

Yerel kayıt ve ses işleme özellikleri için `LOCAL_STUDIO_CHANGES.md` dosyasına bakın.

## Köken ve lisans

Bu yerel çalışma, [UVR5-UI](https://github.com/Eddycrack864/UVR5-UI) ve audio-separator üzerine geliştirilmiştir. Lisans için `LICENSE`, Rubber Band araçlarının lisansı için `tools/rubberband/` içindeki dosyalara bakın.
