# Canlı Çeviri TV — Android TV için canlı İngilizce → Türkçe altyazı

`live-translate/` web uygulamasının Android TV sürümü. İki mod içerir:

- **Ekran çevirisi (arka plan):** TV ekranında görünen İngilizce yazıların üzerine Türkçe çevirisini çizer.
- **Canlı altyazı (konuşma):** İngilizce konuşmayı TV'nin / kumandanın mikrofonundan tanır, Türkçe altyazıyı
  büyük yazıyla ekranda gösterir, isterseniz sesli okur.

- Kotlin + Jetpack Compose for TV, minSdk 21 (Android 5.0+), ana ekranda (Leanback) banner ile görünür.
- Tamamen kumandayla (D-pad) kullanılır. Kumandadaki **mikrofon / arama** tuşu dinlemeyi açar-kapatır
  (sistem asistanı tuşu yakalamıyorsa).
- Arayüz varsayılan **Türkçe**; Ayarlar'dan English seçilebilir.
- API anahtarı **yok**: web uygulamasıyla aynı ücretsiz çeviri zinciri kullanılır.

## Ekran çevirisi modu (arka planda, ekrandaki İngilizce yazılar)

Ana ekrandaki **Ekran çevirisi** düğmesi ya da TV ana ekranındaki ayrı **Ekran Çevirisi** kutucuğu (hızlı aç/kapat)
bir arka plan servisi başlatır. Ekranda İngilizce yazı göründüğünde Türkçe çevirisini **aynı yerin üzerine**,
opak bir kutu içinde çizer. Kumanda alttaki uygulamayı kontrol etmeye devam eder.

Nasıl çalışır:

1. **MediaProjection** ile ekran ~0,8 sn'de bir 1280 px genişliğe küçültülüp yakalanır; ekran değişmediyse
   (kare gelmediyse ya da 96×54 küçük resim aynıysa) OCR atlanır.
2. **ML Kit Text Recognition (Latin, cihaz içi, model APK içinde)** metin bloklarını ve konumlarını bulur.
   Türkçe karakter içeren, rakam ağırlıklı ya da İngilizce olmayan bloklar atlanır.
3. **ML Kit Translation EN→TR (cihaz içi)**: model ilk başlatmada bir kez indirilir (~30 MB). İnene kadar
   (ya da hata olursa) uygulamanın mevcut çevrimiçi zinciri kullanılır (PC sunucusu → Google → Lingva → MyMemory).
   Çeviriler önbelleğe alınır.
4. **TYPE_APPLICATION_OVERLAY** penceresi (odak almaz, dokunma almaz) her bloğun üstüne, arka plan renginden
   örneklenmiş opak bir kutu ve uygun boyutta Türkçe metin çizer.
5. Kendi kutularımızı yeniden okuyup çevirmemek için: yakalama anında overlay ~0,1 sn gizlenir, temiz kare alınır,
   sonra geri gösterilir; kendi değişikliklerimizin ürettiği kareler atılır. Ayrıca son üretilen Türkçe metinler
   OCR sonuçlarından filtrelenir.

### İzinler (bir kez)

**Diğer uygulamaların üzerinde gösterme (overlay).** Uygulama içinden *Üstte gösterme iznini aç* düğmesi
ayar sayfasını açmayı dener. Çoğu Android TV'de bu sayfa **yoktur**; bilgisayardan bir kez:

```bash
adb connect <TV-IP>:5555
adb shell appops set com.qquaq.livetranslatetv SYSTEM_ALERT_WINDOW allow
```

**Ekran yakalama onayı.** Her başlatmada sistem "kayıt/yayın başlatılsın mı?" penceresi çıkar (Android
güvenlik kuralı; Android 14+ onay tekrar kullanılamaz). Pencereyi atlamak ya da penceresi olmayan TV'ler için:

```bash
adb shell appops set com.qquaq.livetranslatetv PROJECT_MEDIA allow
```

Android 13+ ön plan servis bildirimi için bildirim izni de sorulur (reddedilse de servis çalışır).

### Sınırlar — mutlaka okuyun

- **Korumalı içerik siyah görünür:** Netflix, Disney+, Prime Video gibi `FLAG_SECURE` / DRM kullanan uygulamalar
  ekran yakalamada siyah gelir → o uygulamalarda çeviri **yapılamaz**.
- **HDMI girişleri (ör. TV'ye bağlı PS5, uydu alıcısı):** TV'lerin çoğunda HDMI görüntüsü HDCP / donanım katmanıyla
  gösterilir ve MediaProjection'da siyah görünür → çoğu TV'de **çalışmaz**. (Bazı TV'lerde HDCP kapalı kaynaklar
  görünebilir; cihaza bağlı.)
- Video oynatılırken her karede ekran değiştiği için OCR sürekli çalışır ve kutular saniyede bir kısa süre yanıp söner.
- OCR yalnızca Latin alfabesi; çok küçük, stilize ya da hareketli yazılar kaçabilir. Kutular çeviri uzunsa aşağı doğru uzar.
- Düşük güçlü TV işlemcilerinde OCR + çeviri 0,3–1 sn sürebilir; bu sürede yeni yazı gecikmeli görünür.
- APK, OCR modelini tüm işlemci türleri için içerdiğinden ~58 MB'dır.

## Nasıl çalışır (web sürümüyle eşleşme)

| Web (`live-translate/`) | TV (`live-translate-tv/`) |
| --- | --- |
| Tarayıcı `SpeechRecognition` (en-US, continuous) | Android `SpeechRecognizer` (en-US, kısmi sonuçlar, her cümleden sonra yeniden başlar) |
| `lib/translate.ts`: `/api/translate` → Lingva → MyMemory | `Translator.kt`: PC sunucusu `/api/translate` (ayarlanmışsa) → Google `gtx` (sunucunun kullandığı uç nokta) → Lingva → MyMemory |
| `speechSynthesis` tr-TR, sıralı okuma | Android `TextToSpeech` tr-TR, `QUEUE_ADD` |
| Son 4 Türkçe satır, ara sonuçta "…" | Aynı |

PC sunucusu (`sunucu.bat` / `sunucu.sh`, port 3456) isteğe bağlıdır: Ayarlar → *PC çeviri sunucusu* alanına
`http://192.168.x.x:3456` yazarsanız TV önce o sunucuyu kullanır; boşsa servislere doğrudan bağlanır.

## Derleme

Gerekenler: JDK 17+ ve Android SDK (platform 35). Android Studio ile `live-translate-tv/` klasörünü açmak yeterli,
ya da komut satırından:

```bash
cd live-translate-tv
echo "sdk.dir=$HOME/Android/Sdk" > local.properties   # SDK yolunuz
./gradlew assembleDebug
# çıktı: app/build/outputs/apk/debug/app-debug.apk
```

Her PR / `main` push'unda GitHub Actions (`.github/workflows/live-translate-tv-apk.yml`) debug APK'yı derleyip
**live-translate-tv-debug-apk** adlı artifact olarak yükler (Actions → ilgili çalıştırma → Artifacts).

## TV'ye yükleme (sideload, adb)

1. TV'de **Ayarlar → Cihaz tercihleri → Hakkında → Yapı (Build)** satırına 7 kez basın → geliştirici modu açılır.
2. **Geliştirici seçenekleri → USB hata ayıklama / Ağ üzerinden hata ayıklama (ADB debugging)** açın.
   TV'nin IP adresini **Ayarlar → Ağ** altında bulun.
3. Bilgisayardan:

   ```bash
   adb connect 192.168.1.50:5555          # TV'nin IP'si (Android 11+ Google TV'de "Kablosuz hata ayıklama" eşleştirme kodu isteyebilir: adb pair IP:PORT)
   adb install -r app-debug.apk
   ```

   TV'de çıkan "Bu bilgisayara izin ver" sorusunu onaylayın.
4. Uygulama ana ekranda **Canlı Çeviri TV** olarak görünür (görünmezse **Uygulamalar** listesine bakın).
5. İlk **Mikrofonu aç** basışında mikrofon izni istenir → izin verin.

adb olmadan: APK'yı USB belleğe kopyalayıp TV'de bir dosya yöneticisiyle (ör. *File Commander*) ya da
*Send files to TV* / *Downloader* uygulamasıyla açabilirsiniz ("bilinmeyen kaynaklar" izni gerekir).

## Kullanım

- **Mikrofonu aç / Durdur** (ilk odak burada), **Temizle**, **Sesli okuma: Açık/Kapalı**, **Ayarlar**.
- Ayarlar: arayüz dili (Türkçe / English), isteğe bağlı PC sunucu adresi ve **Sunucuyu dene** düğmesi.

## Mikrofonsuz test (yalnızca debug APK)

Emülatörde ya da mikrofonsuz bir cihazda çeviri zincirini denemek için metni "tanınmış gibi" gönderebilirsiniz:

```bash
adb shell "am start -n com.qquaq.livetranslatetv/.MainActivity --es debug_text 'Good evening and welcome to the news.'"
```

Release derlemelerde bu kanca devre dışıdır.

## Bilinen sınırlamalar

- Konuşma tanıma cihazdaki Google konuşma servisine bağlıdır; bazı TV'lerde (Google uygulaması olmayan
  Android TV'ler) "konuşma tanıma servisi yok" hatası çıkabilir.
- Bluetooth kumanda mikrofonunun uygulama içinden sürekli dinleme için kullanılabilmesi cihaza/kumandaya göre değişir;
  dahili mikrofonu olan TV'lerde ya da USB/Bluetooth mikrofonla en iyi çalışır.
- Android'in `SpeechRecognizer`'ı cümle bitince durur; uygulama otomatik yeniden başlatır, aradaki kısa sürede
  söylenen kelimeler kaçabilir.
- Çeviri servisleri ücretsiz/resmî olmayan uç noktalardır; kota dolarsa "Çeviri kotası…" hatası görünür.
