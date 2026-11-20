# PS5 Altyazı Çevirmeni (PC) — GTA 6 İngilizce altyazı → TV'de Türkçe

PS5 görüntüsü TV'ye HDMI ile gider. TV'deki uygulama HDMI görüntüsünü **okuyamaz**, ama üstüne **yazı çizebilir**.
Bu yüzden İngilizce altyazıyı **bilgisayar** okur:

```
PS5 ──HDMI──► Onvo TV  (Canlı Çeviri TV uygulaması, "Ağ alıcısı" Türkçeyi oyunun üstüne çizer)
 │                ▲
 └─Remote Play──► PC (bu program: altyazıyı okur → Türkçeye çevirir → Wi‑Fi ile TV'ye yollar)
```

Türkçe yazı, İngilizce altyazının **tam üstüne** siyah bir kutu içinde gelir. Gecikme yaklaşık 1 saniyedir.

## Gerekenler

- Windows 10 veya 11 bilgisayar (PS5 ve TV ile **aynı ev ağında**; kablolu bağlantı en iyisi)
- TV'de **Canlı Çeviri TV** uygulaması (APK)
- PS5 hesabınız (PlayStation Network)
- İnternet (çeviri internetten yapılır, anahtar/üyelik gerekmez)

---

## Bu akşam için adım adım

### A) TV: uygulamayı kurun ve izni verin (bir kez)

1. TV uygulamasının (`live-translate-tv`) README'sindeki **"Onvo 55VQ90F3UA kurulumu"** bölümünde
   **2, 3 ve 5. adımları** yapın:
   - 2: Geliştirici seçeneklerini açın.
   - 3: APK'yı kurun (telefondan *Send Files to TV* ya da bilgisayardan `adb install -r app-debug.apk`).
   - 5: **Üstte gösterme izni**. Bilgisayarda, TV'ye `adb connect` ile bağlıyken:

     ```
     adb shell appops set com.qquaq.livetranslatetv SYSTEM_ALERT_WINDOW allow
     adb shell appops get com.qquaq.livetranslatetv SYSTEM_ALERT_WINDOW
     ```

     İkinci komut `allow` yazmalı. Bu izin olmadan TV'de hiçbir yazı çıkmaz.
2. TV'de **Canlı Çeviri TV → Ekran çevirisi → Ağ alıcısını aç**'a basın. Ekranda iki şey yazar:
   - **adres**: `http://192.168.x.x:8765`
   - **8 karakterlik eşleştirme kodu**

   İkisini de not edin. (Ekran yakalama onayı **gerekmez**.)
3. TV'nin girişini **PS5'in HDMI'sine** alın. Alıcı arka planda çalışmaya devam eder.

### B) PS5: Remote Play'i açın (bir kez)

1. PS5'te **Ayarlar → Sistem → Uzaktan Oynatma → Uzaktan Oynatmayı Etkinleştir**: açık.
2. İsteğe bağlı: **Ayarlar → Sistem → Güç Tasarrufu → Dinlenme Modunda Kullanılabilen Özellikler →
   İnternete Bağlı Kal** açık olursa PC, PS5'i uykudan da uyandırabilir.

### C) PC: PS Remote Play'i kurun ve bağlanın

1. [PS Remote Play for Windows](https://remoteplay.dl.playstation.net/remoteplay/lang/tr/)'ı indirip kurun.
2. Açın, PS5'teki **aynı PlayStation hesabıyla** oturum açın, **PS5**'i seçin. Bağlanınca PC'de oyun
   görüntüsü çıkar. TV'de de görüntü aynen devam eder; oyunu her zamanki gibi **PS5'e bağlı kumandayla**
   oynayın.
3. Remote Play ayarlarında (bağlanmadan önce dişli simgesi) **Video kalitesi → Çözünürlük: 1080p** seçin.
   Yazı ne kadar netse okuma o kadar iyi olur.
4. **Sesi kapatın:** sesi TV'den duyuyorsunuz. Windows ses karıştırıcısında *PS Remote Play* sesini kısın.

> **Önemli — Remote Play penceresi:**
> - Pencereyi **simge durumuna küçültmeyin** (görev çubuğuna indirmeyin). Küçültülmüş pencere okunamaz.
> - Pencere **başka pencerelerin arkasında kalabilir** (varsayılan "Otomatik" yöntem bunu dener). Arkadayken
>   Türkçe gelmiyorsa pencereyi görünür bırakın ya da ikinci bir monitöre taşıyın ve yöntemi
>   **"Ekrandan kopyala"** yapın.
> - Pencereyi çok küçültmeyin (genişlik en az ~960 piksel olsun).
> - Remote Play yerine **chiaki-ng** de kullanılabilir; program onun penceresini de tanır.

### D) PC: bu programı çalıştırın

1. **İndirin:** `PS5Altyazi-windows.zip`. Kaynağı: GitHub'da PR → **Checks → Build ps5-subtitle-pc →
   Artifacts → PS5Altyazi-windows**. Zip'i bir klasöre çıkarın (zip içinden çalıştırmayın).
2. `PS5Altyazi\PS5Altyazi.exe`'yi çift tıklayın (ya da `baslat.bat`). Python kurmanız **gerekmez**.
   - "Windows kişisel bilgisayarınızı korudu" uyarısı çıkarsa: **Ek bilgi → Yine de çalıştır**.
   - Windows Güvenlik Duvarı sorarsa **İzin ver** (Özel ağ).
3. Programda:
   1. **TV IP adresi**: TV'de yazan adres (ör. `192.168.1.50`; `:8765` yazmanız gerekmez).
      **Eşleştirme kodu**: TV'deki 8 karakter. **Bağlantıyı dene**'ye basın. TV'de 4 saniye boyunca
      *"Bağlantı tamam"* yazısı çıkmalı.
   2. **Görüntü kaynağı**: *PS Remote Play / chiaki-ng penceresi*. Liste kendiliğinden "PS Remote Play"
      penceresini seçer; seçmezse **Yenile**'ye basıp listeden seçin.
   3. **Bölgeyi ayarla…**: oyundan bir kare açılır. Yeşil kutu, İngilizce altyazının çıktığı alt bölgeyi
      kapsamalı (varsayılan: ekranın alt dörtte biri). Gerekirse fareyle yeniden çizin → **Kaydet**.
   4. **▶ BAŞLAT**. Altyazı çıktıkça programda *EN / TR* satırları görünür, TV'de Türkçe yazı belirir.
   5. Bitince **■ DURDUR**. Ayarlar kaydedilir; bir dahaki sefere sadece BAŞLAT yeterli.

**GTA 6 içinde:** Ayarlar → Ekran/Görüntü → **Altyazılar: Açık**. Varsa *altyazı arka planı*nı açın ve altyazı
boyutunu büyütün. Okuma kolaylaşır.

## Seçenekler

- **Türkçeyi İngilizcenin üstüne yaz** (varsayılan) ya da **ekranın en altına yaz**.
- **PC'de önizleme penceresi**: Türkçeyi PC'de de büyük yazıyla gösterir. TV'siz denemek için **TV'ye gönder**'i kapatın.
- **Yakalama kartı**: HDMI geçişli bir capture kartınız varsa (PS5 → kart → TV, kart USB ile PC'ye) bu kaynağı
  seçin. Kart no genelde `0`'dır. PS5'te **Ayarlar → Sistem → HDMI → HDCP'yi Etkinleştir: kapalı** olmalı.
- **Kayıttan test**: bir oyun videosu ya da ekran görüntüsü klasörü seçerek PS5 olmadan deneyin.

## Sorun giderme

| Belirti | Çözüm |
| --- | --- |
| "TV'ye ulaşılamadı" | TV'de **Ağ alıcısını aç** açık mı? IP doğru mu? PC ve TV aynı modemde mi (misafir ağı değil)? |
| "Eşleştirme kodu yanlış" | Kod alıcı her açıldığında değişebilir. TV'deki güncel kodu girin. |
| "Bağlantı tamam" diyor ama TV'de yazı yok | TV'de üstte gösterme izni yok → A-1'deki `adb shell appops ... allow` komutu. |
| "Pencere simge durumuna küçültülmüş" | Remote Play penceresini görev çubuğundan geri açın. |
| Altyazı okunuyor ama TV'de geç ya da hiç çıkmıyor | Programdaki kayıt alanında `!` ile başlayan hata satırlarına bakın. "Çeviri kotası" yazıyorsa biraz bekleyin. |
| Yanlış yer okunuyor (harita, para) | **Bölgeyi ayarla** ile kutuyu sadece altyazı alanına daraltın. |
| Arkadayken çalışmıyor | Yöntemi **Ekrandan kopyala** yapın, Remote Play penceresini görünür bırakın. |

Kayıt dosyası: `%APPDATA%\PS5Altyazi\` (ayarlar `ayarlar.json`).

## Teknik notlar (geliştiriciler için)

- **OCR: RapidOCR** (PaddleOCR modelleri, ONNX Runtime, CPU). Modeller pip paketinin içinde gelir: indirme ya da
  dil paketi gerekmez, PyInstaller ile tek klasöre paketlenir. 1280×180 kırpıntıda ~0,4 sn. Windows.Media.Ocr
  daha hızlıdır ama İngilizce OCR dil paketi ister; Türkçe Windows'larda bu paket çoğu zaman yoktur.
- **Kararlılık:** altyazı iki karede aynı (bulanık eşleşme) okunmadan gönderilmez. Aynı altyazı için tekrar
  çeviri yapılmaz, 3 boş kareden sonra TV'deki yazı silinir. Görüntü değişmediyse OCR atlanır. TV'deki kutu
  `ttlMs` (15 sn) sonra kendiliğinden kaybolur; altyazı ekranda kaldıkça program kutuyu tazeler.
- **Çeviri:** `live-translate/lib/translate.ts` ile aynı anahtarsız zincir: Google `gtx` → Lingva → MyMemory.
  `pip install argostranslate` ve en→tr paketi kuruluysa çevrimdışı yedek olarak Argos kullanılır.
  "Jason: …" gibi konuşmacı adları çevrilmeden korunur.
- **TV protokolü:** `POST /overlay` (`boxes`, normalize koordinat, `lines`), `DELETE /overlay`, `GET /status`,
  `GET /ping`, `X-Token` başlığı. TV uygulamasında değişiklik gerekmez.
- **Pencere yakalama:** `PrintWindow(PW_RENDERFULLCONTENT)` kullanılır, siyah gelirse ekrandan kopyalanır
  (`mss`). Remote Play'in pencere içindeki siyah şeritleri kırpılır, böylece bölge oyun görüntüsüne göre
  hesaplanır.

Geliştirme (Python 3.12):

```bash
cd ps5-subtitle-pc
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                       # birim + uçtan uca (örnek kareler → OCR → sahte TV)
python tools/mock_tv.py 8765 secret12     # sahte TV alıcısı
python -m ps5sub                          # arayüz
python -m ps5sub --cli --source file --value samples --tv 127.0.0.1:8765 --token secret12
python -m ps5sub --self-test              # paketlenmiş exe kontrolü
```

`samples/` klasöründeki kareler `tools/make_samples.py` ile üretilmiş GTA tarzı test görüntüleridir.
GitHub Actions (`.github/workflows/ps5-subtitle-pc.yml`) Windows'ta testleri çalıştırır, exe'yi derler ve
`--self-test` ile dener. Sahte bir "PS Remote Play" penceresini iki yöntemle yakalar ve sonucu
`PS5Altyazi-windows` artifact'ı olarak yükler.
