# PS5 Mirror (ilk prototip, Windows odakli)

PS5'in goruntusunu ve sesini Windows bilgisayarda gosterir. Goruntu/ses akisi
**PS Remote Play protokolu** ile [chiaki-ng](https://github.com/streetpea/chiaki-ng)
tarafindan saglanir; bu proje onun uzerine ayar, konsol bulma ve tek tikla
baslatma katmani ekler. HDMI yakalama karti **gerekmez**.

> Durum: prototip. Arayuz, ayarlar, konsol kesfi paketleri ve surec yonetimi
> otomatik testlidir; **gercek bir PS5 ile akis henuz test edilmemistir** (bkz. "Bilinenler").

## Gereksinimler (Windows 10/11)

1. **Python 3.9+** — `winget install Python.Python.3.12` (baska paket gerekmez)
2. **chiaki-ng** — [GitHub Releases](https://github.com/streetpea/chiaki-ng/releases)
   sayfasindan Windows surumunu indirip kurun/acin.
3. PS5 ve bilgisayar **ayni yerel agda** (Wi-Fi 5 GHz veya tercihen kablolu), PS5'te
   *Ayarlar > Sistem > Uzaktan Oynatma > Uzaktan Oynatmayi Etkinlestir* acik.
   Dinlenme modundan uyandirmak istiyorsaniz *Guc Tasarrufu > Ozellikler > Dinlenme
   Modunda Kullanilabilir Ozellikler* altinda ag/uyanma seceneklerini acin.

## Tek komutla calistirma

Klasorde `ps5mirror.bat` dosyasina cift tiklayin ya da PowerShell/CMD'de:

```bat
ps5mirror.bat
```

(Python varsa `py -3 -m ps5mirror` de ayni isi yapar; bagimlilik yoktur.)
Tarayicinizda yerel arayuz (`http://127.0.0.1:8765`) acilir.

## Ilk kurulum (bir kerelik)

1. **chiaki-ng'yi acin**, `+` ile konsolu ekleyin: PS5'in IP adresi, PSN hesap kimliginiz
   (Account ID) ve PS5'te *Uzaktan Oynatma > Aygit Bagla* ekranindaki 8 haneli kod.
   Konsola verdiginiz adi not edin (ornek: `PS5`).
2. `ps5mirror.bat` ile arayuzu acin, **Agda ara** ile PS5'i bulun (ya da IP'yi yazin),
   gerekirse *chiaki-ng profil adi* alanina chiaki-ng'deki kayit adini girin,
   **Ayarlari kaydet** > **Baslat**.

Ayar dosyasi: `%APPDATA%\ps5mirror\config.json`.

## Komut satiri

```bat
ps5mirror.bat check          :: ayar + chiaki-ng bulundu mu?
ps5mirror.bat discover       :: agdaki PS5'leri listele
ps5mirror.bat start          :: kayitli ayarlarla baslat
set "PS5_CREDENTIAL=<regist anahtari>"
ps5mirror.bat wake --host 192.168.1.50
```

`pip install .` yaparsaniz `ps5mirror` komutu da kurulur.

## Test

```bash
python -m unittest discover -s tests -v
```

## Bilinenler / sinirlar

- Gercek PS5 olmadan **dogrulanmayanlar**: chiaki-ng `stream <profil> <host>` komut bicimi
  (uymazsa ayarda `extra.remoteplay_template` ile degistirilir), kesif paketi bicimi
  (PS5 icin UDP 9302) ve uyandirma paketi (UDP 9295), gercek akis kalitesi/gecikme.
- Windows'ta bu kod calistirilarak denenmedi (testler Linux'ta kosuldu); yol arama ve
  `.bat` baslaticisi Windows kurallarina gore yazildi.
- Kayit (registration) ve PSN kimlik islemleri chiaki-ng'de yapilir; bu uygulama sifre/anahtar saklamaz.
- Arayuz yalnizca `127.0.0.1` uzerinde dinler.
- Uygulama Sony ile bagli degildir; Remote Play protokolu gayriresmi olarak chiaki tarafindan uygulanmistir.
