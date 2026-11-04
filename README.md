# PS5 Mirror (ilk prototip, Windows odakli)

PS5'in goruntusunu bilgisayarda gosterir. Iki mod vardir:

1. **payload (varsayilan):** Jailbreak'li PS5'e bir **ELF payload** gonderilir; payload konsolun
   kendi donanim H.264 kodlayicisindan goruntuyu alip **HTTP portundan (7231)** sunar. Bu program
   ELF'i konsola gonderir, akisi cozer ve `ffplay` penceresinde gosterir. **PSN hesabi ve HDMI
   yakalama karti gerekmez.**
2. **remoteplay:** PS Remote Play protokolu ([chiaki-ng](https://github.com/streetpea/chiaki-ng)
   uzerinden). PSN girisi gerektirir; PSN'e girilemeyen konsolda calismaz.

> Durum: prototip. Bilgisayar tarafi (ELF gonderme, HTTP akisini cozme, oynatici, arayuz,
> ayarlar) otomatik testli ve sahte payload ile uctan uca denendi. **Gercek bir PS5 ile hicbir
> sey test edilmedi.**

## PS5 tarafi: payload nereden gelir?

Bu repo PS5 payload'i yazmaz/icermez; var olan acik kaynak calismalar kullanilir:

| Ne | Not |
|---|---|
| [ps5-payload-dev/sdk](https://github.com/ps5-payload-dev/sdk) | Acik kaynak (GPLv3) PS5 payload SDK'si (clang/LLVM 18 ile derleme); ELF'ler ELF loader'a 9021 portundan gonderilir |
| [MiladRTX/Glint](https://github.com/MiladRTX/Glint) | Hazir payload (`Glint-1.3-ps5.elf`) + Windows uygulamasi (`Glint.exe`). HTTP API `7231` portunda, H.264 `/frames`, ses `/audio`. README'sine gore **firmware 13.60'ta test edilmis**, yalnizca 60 Hz modunda calisir. **Bu programin payload modu bu API'ye gore yazildi.** |
| [Darkatek7/ProsperoSunshine](https://github.com/Darkatek7/ProsperoSunshine) | Moonlight uyumlu akis sunucusu (ses, goruntu, kontrolcu); 13.00 test edilmis, 13.60 icin kullanici raporlari var |

Hizli yol istiyorsaniz Glint'in kendi `Glint.exe`'si bu programdan daha olgundur (GPU cozme, ses
senkronu, kayit). Bu programin farki: sade, bagimliliksiz Python + ffplay, ayni API'yi kullanir.

**Guvenlik:** Konsola gonderdiginiz ELF, konsolda yuksek yetkiyle calisir. Yalnizca guvendiginiz
kaynaktan, surum sayfasindaki SHA256 ile dogrulayarak kullanin. Konsolu jailbreak'lemek bu projenin
konusu degildir; bu repo jailbreak yontemi, exploit veya korsan icerikle ilgili bir sey icermez.

## Gereksinimler (Windows 10/11)

1. **Python 3.9+** — `winget install Python.Python.3.12`
2. **FFmpeg (ffplay)** — `winget install Gyan.FFmpeg` (yeni bir terminal acin)
3. PS5'te ELF loader acik (varsayilan port 9021) ve payload ELF dosyasi bilgisayarda
4. PS5 ve PC ayni aginda (tercihen kablolu; Wi-Fi'da daha fazla gecikme/titreme olur)

## Tek komutla calistirma

Klasorde `ps5mirror.bat` dosyasina cift tiklayin ya da PowerShell/CMD'de:

```bat
ps5mirror.bat
```

Tarayicida yerel arayuz (`http://127.0.0.1:8765`) acilir: PS5 IP adresini girin, ELF yolunu
yazip **ELF'i gonder**'e basin, konsolda payload'in "ready" demesini bekleyin, **Baslat**.

Komut satirindan:

```bat
ps5mirror.bat send-elf C:\indirilenler\Glint-1.3-ps5.elf --host 192.168.1.50
ps5mirror.bat check
ps5mirror.bat start
```

Ayar dosyasi: `%APPDATA%\ps5mirror\config.json` (`host`, `payload_port`, `loader_port`, `audio`).
Ses (`audio: true`) deneysel: ayri bir ffplay'e verilir, goruntuyle senkron degildir.

## PS5 olmadan deneme

```bash
python tools/fake_payload.py          # ffmpeg ile test deseni akitan sahte payload (127.0.0.1:7231)
# arayuzde host=127.0.0.1 secip Baslat
```

---

## Remote Play modu (PSN gerektirir)

Ayarlarda `mode: "remoteplay"` secilir (arayuzde Mod listesi). Remote Play kaydi icin PSN hesabi ve
konsolda *Uzaktan Oynatma > Aygit Bagla* kodu gerekir; PSN'e girilemeyen eski sistem yazilimlarinda
calisip calismayacagi **dogrulanmadi**. Bu durumda payload modunu kullanin.

1. **chiaki-ng** kurun ([Releases](https://github.com/streetpea/chiaki-ng/releases)) ve acip `+` ile
   konsolu kaydedin (IP, PSN Account ID, konsoldaki 8 haneli kod).
2. Arayuzde modu *PS Remote Play* yapin, host ve (gerekirse) chiaki-ng profil adini girin, **Baslat**.

```bat
ps5mirror.bat discover       :: agdaki PS5'leri bul (Remote Play acik olmali)
set "PS5_CREDENTIAL=<regist anahtari>"
ps5mirror.bat wake --host 192.168.1.50
```

## Test

```bash
python -m unittest discover -s tests -v
```

## Bilinenler / sinirlar

- **Gercek PS5 ile dogrulanmayanlar:** payload'a ELF gonderme, Glint API'si ile gercek akis
  (cerceve bicimi Glint `docs/API.md`'ye gore yazildi), firmware 13.60 uyumu, gecikme, ses,
  chiaki-ng komut bicimi, Remote Play kesif (UDP 9302) ve uyandirma (UDP 9295) paketleri.
- Windows'ta calistirilarak denenmedi (testler ve ffplay denemesi Linux'ta yapildi).
- Payload tek izleyiciye hizmet eder: Glint.exe veya tarayici paneli aciksa 409 doner; once onlari kapatin.
- Glint yalnizca 1080p60 ve 60 Hz ekran modunda calisir (payload'in kendi siniri).
- Arayuz yalnizca `127.0.0.1` uzerinde dinler; `/api/send-elf` yalnizca `.elf` uzantili yerel dosyalari gonderir.
- Uygulama Sony ile baglantili degildir.
