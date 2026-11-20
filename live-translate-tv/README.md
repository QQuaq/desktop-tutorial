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

## Onvo 55VQ90F3UA (Google TV) kurulumu — adım adım

Bu TV Google TV kullanır (Android TV 12 ya da 14, MediaTek işlemci). Menü adları yazılım sürümüne göre biraz
farklı olabilir. Ekran çevirisinin üstte gösterme iznini Google TV'de menüden açmak **mümkün değil**, bu yüzden
kurulumdan sonra **bir kez** `adb` komutu çalıştırmanız gerekir (5. adım). Bunun için bir bilgisayar gerekir;
alternatif olarak bir Android telefondaki *Bugjaeger* gibi bir adb uygulaması da kullanılabilir.

### 1. Android sürümünü öğrenin

**Ayarlar (⚙) → Sistem → Hakkında → Android TV OS sürümü.** 12 ya da 14 yazar. Aşağıda farklı olan adımlar
ayrıca belirtilmiştir.

### 2. Geliştirici seçeneklerini açın

1. **Ayarlar → Sistem → Hakkında** sayfasında en alttaki **Android TV OS derlemesi** satırına gelin.
2. Kumandada **OK** tuşuna arka arkaya **7 kez** basın. PIN isterse TV'nin PIN'ini girin.
   "Artık bir geliştiricisiniz" mesajı çıkar.
3. **Ayarlar → Sistem → Geliştirici seçenekleri** artık görünür.

### 3. APK'yı TV'ye kurun (iki yoldan birini seçin)

APK'yı alın: GitHub'da PR'ın **Checks → Build live-translate-tv APK → Artifacts** bölümünden
`live-translate-tv-debug-apk` zip'ini indirip içindeki `app-debug.apk` dosyasını çıkarın.

**Yol A — Telefondan "Send Files to TV" ile (kablosuz, bilgisayarsız):**

1. TV'de **Google Play Store**'dan **Send Files to TV** uygulamasını kurun; telefona da aynı uygulamayı kurun.
2. TV'de **Ayarlar → Uygulamalar → Güvenlik ve kısıtlamalar → Bilinmeyen kaynaklar** sayfasında
   **Send Files to TV**'yi **açık** yapın. Android 14'te bu izin, ilk kurulum denemesinde de sorulabilir.
3. Telefonda Send Files to TV → **Gönder** → `app-debug.apk` → TV'nizi seçin.
4. TV'de Send Files to TV → **Alınanlar** (Received) → `app-debug.apk` → **Yükle**.
   "Play Protect" uyarısı çıkarsa **Yine de yükle**'yi seçin.

**Yol B — Bilgisayardan adb ile (Wi‑Fi):**

1. Bilgisayara [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) indirin
   (`adb` bunun içindedir).
2. TV'nin IP adresini bulun: **Ayarlar → Ağ ve İnternet →** bağlı Wi‑Fi ağı → IP adresi (ör. `192.168.1.50`).
3. Bağlantıyı açın:
   - **Android TV 12:** **Geliştirici seçenekleri → USB hata ayıklama** açık. Sonra bilgisayarda:

     ```bash
     adb connect 192.168.1.50:5555
     ```

     TV'de "USB hata ayıklamaya izin verilsin mi?" sorusu çıkar; **Bu bilgisayara her zaman izin ver** → **Tamam**.
   - **Android TV 14:** **Geliştirici seçenekleri → Kablosuz hata ayıklama** açın → **Cihazı eşleme koduyla eşle**.
     TV bir **IP:port** ve **6 haneli kod** gösterir. Bilgisayarda:

     ```bash
     adb pair 192.168.1.50:<eşleme-portu>      # kodu girin
     adb connect 192.168.1.50:<bağlantı-portu>  # Kablosuz hata ayıklama ekranındaki IP:port
     ```

4. Kurun: `adb install -r app-debug.apk`

### 4. Uygulamayı bulun

Google TV'de yüklenen uygulamalar ana sayfada değil, **Uygulamalar** sekmesinde (ya da *Uygulamalarınız → Tümünü
gör*) görünür. İki kutucuk vardır: **Canlı Çeviri TV** (uygulama) ve **Ekran Çevirisi** (tek tıkla aç/kapat).
Kutucuğun üzerinde OK'a basılı tutup favorilere ekleyebilirsiniz.

### 5. Üstte gösterme iznini verin (bir kez, adb ile)

Google TV'de *Diğer uygulamaların üzerinde göster* ayar sayfası yoktur. 3B adımındaki gibi bağlıyken:

```bash
adb shell appops set com.qquaq.livetranslatetv SYSTEM_ALERT_WINDOW allow
adb shell appops get com.qquaq.livetranslatetv SYSTEM_ALERT_WINDOW   # "allow" yazmalı
```

İsteğe bağlı olarak, her başlatmada çıkan ekran yakalama onayını atlamak için (bazı TV'lerde bu onay penceresi hiç yoktur):

```bash
adb shell appops set com.qquaq.livetranslatetv PROJECT_MEDIA allow
```

İzinler TV yeniden başlasa da kalır. Uygulama kaldırılıp yeniden kurulursa komutları tekrar çalıştırın. İş bitince
**Geliştirici seçenekleri → USB / Kablosuz hata ayıklama**'yı kapatabilirsiniz.

### 6. Ekran çevirisini başlatın

1. **Canlı Çeviri TV → Ekran çevirisi → Ekran çevirisini başlat** (ya da ana ekrandaki **Ekran Çevirisi** kutucuğu).
2. Android 13+ bildirim izni sorarsa **İzin ver**. Reddederseniz de çalışır, yalnızca bildirim görünmez.
3. "Kayıt veya yayın başlatılsın mı?" penceresinde **Şimdi başlat**. **Android 14'te bu onay her başlatmada
   yeniden istenir**; onay bir sonraki oturumda tekrar kullanılamaz. Bunun tek istisnası `PROJECT_MEDIA` adb komutudur.
4. **Ana ekran** tuşuyla çıkın ve İngilizce yazı olan bir uygulamayı açın. Türkçe kutular birkaç saniye içinde belirir.
   Cihaz içi çeviri modeli ilk seferde (~30 MB) inene kadar çeviriler internetten yapılır.
5. Durdurmak için **Ekran Çevirisi** kutucuğuna tekrar basın, uygulamadaki **Durdur** düğmesini kullanın ya da
   bildirimdeki **Tümünü durdur**'a basın.

### Android 12 ve 14 farkları

| | Android TV 12 | Android TV 14 |
| --- | --- | --- |
| Ekran yakalama onayı | Her başlatmada sorulur | Her başlatmada sorulur ve onay yeniden kullanılamaz |
| Ön plan servis türü | `mediaProjection` | Ekran çevirisi için `mediaProjection`, ağ alıcısı için `specialUse` |
| Kablosuz adb | `adb connect IP:5555` | *Kablosuz hata ayıklama* + `adb pair` |
| Bildirim izni | Sorulmaz | Sorulur (Android 13+) |

### Sorun giderme

- **Kutular hiç çıkmıyor:** `adb shell appops get com.qquaq.livetranslatetv SYSTEM_ALERT_WINDOW` → `allow` olmalı.
  Uygulamadaki **Ekran çevirisi** sayfasında *Üstte gösterme izni: Var* yazmalı.
- **"Onay penceresi yok" hatası:** `PROJECT_MEDIA allow` komutunu çalıştırın.
- **Netflix / Disney+ / HDMI (PS5) üzerinde çalışmıyor:** bu beklenen bir durum, aşağıdaki *Sınırlar* bölümüne bakın.
  HDMI için **Ağdan çeviri alıcı** tasarlandı.
- **Servis kendiliğinden kapandı:** Android ekran paylaşımını durdurmuş olabilir (ör. TV bekleme moduna girdi). Yeniden başlatın.

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
4. **TYPE_APPLICATION_OVERLAY** penceresi (odak almaz, kumanda tuşları alttaki uygulamaya gider) her bloğun üstüne,
   arka plan renginden örneklenmiş opak bir kutu ve uygun boyutta Türkçe metin çizer. Android 12+ dokunma almayan
   overlay'leri %80 opaklıkla sınırladığından (İngilizce alttan görünür), TV'lerde pencere dokunmayı alır; fare/dokunma
   kullanan nadir TV'lerde çeviri açıkken tıklama alttaki uygulamaya geçmez.
5. Kendi kutularımızı yeniden okuyup çevirmemek için: yakalama anında overlay ~0,1 sn gizlenir, temiz kare alınır,
   sonra geri gösterilir; kendi değişikliklerimizin ürettiği kareler atılır. Ayrıca son üretilen Türkçe metinler
   OCR sonuçlarından filtrelenir.

İzinler için yukarıdaki Onvo kurulumunun 5. ve 6. adımlarına bakın.

### Sınırlar — mutlaka okuyun

- **Korumalı içerik siyah görünür:** Netflix, Disney+, Prime Video gibi `FLAG_SECURE` / DRM kullanan uygulamalar
  ekran yakalamada siyah gelir, bu yüzden o uygulamalarda OCR çevirisi **yapılamaz**.
- **HDMI girişleri (ör. TV'ye bağlı PS5, uydu alıcısı):** HDMI görüntüsü HDCP ve donanım katmanıyla ("sideband")
  gösterildiği için ekran yakalamada **siyah** görünür. TV içindeki uygulama bu görüntüyü **okuyamaz**. Ancak yerleşik
  Google TV'lerde overlay HDMI görüntüsünün **üstüne çizebilir**. Bu nedenle HDMI için çeviriyi başka bir cihaz
  yapar ve **Ağdan çeviri alıcı** (aşağıda) ile TV'ye gönderir.
- **Sistem ekranları:** TV Ayarları ve izin pencereleri açıkken Android tüm overlay'leri gizler; bu ekranlar
  çevrilemez. Test için tarayıcı, YouTube ya da Google TV ana ekranını kullanın.
- Video oynatılırken her karede ekran değiştiği için OCR sürekli çalışır ve kutular saniyede bir kısa süre yanıp söner.
  Ekran durağansa kutular yerinde kalır, yanıp sönme olmaz.
- OCR yalnızca Latin alfabesi; çok küçük, stilize ya da hareketli yazılar kaçabilir. Kutular çeviri uzunsa aşağı doğru uzar.
- Düşük güçlü TV işlemcilerinde OCR + çeviri 0,3–1 sn sürebilir; bu sürede yeni yazı gecikmeli görünür.
- APK, OCR modelini tüm işlemci türleri için içerdiğinden ~58 MB'dır.

## Ağdan çeviri alıcı (deneysel — PC / telefon tarafı henüz yok)

HDMI kaynakları (PS5 vb.) için çeviriyi TV dışında bir cihaz yapar: örneğin PS Remote Play görüntüsünü okuyan
bir PC ya da telefon. TV tarafında **Ekran çevirisi → Ağ alıcısını aç** düğmesine basın. Ekran yakalama onayı
gerekmez, yalnızca üstte gösterme izni (5. adım) gerekir. Ekranda adres (`http://<TV-IP>:8765`) ve 8 karakterlik
**eşleştirme kodu** görünür. Gönderen cihaz aynı yerel ağda olmalıdır.

Protokol (HTTP/JSON, her istekte `X-Token: <kod>` başlığı, `Authorization: Bearer <kod>` ya da `?token=<kod>`):

| İstek | Açıklama |
| --- | --- |
| `GET /ping` | Kod gerekmez; `{"app":"live-translate-tv"}` |
| `GET /status` | Ekran çözünürlüğü (`screen.width/height`) ve durum |
| `POST /overlay` | Ağdan gelen kutuları **değiştirir** (OCR kutularına dokunmaz) |
| `DELETE /overlay` ya da `POST /clear` | Ağdan gelen kutuları siler |

`POST /overlay` gövdesi:

```json
{
  "coords": "normalized",
  "ttlMs": 8000,
  "boxes": [
    { "x": 0.10, "y": 0.82, "w": 0.80, "h": 0.08, "text": "Görev tamamlandı", "lines": 1,
      "bg": "#E6000000", "fg": "#FFFFFF" }
  ]
}
```

- `coords`: `normalized` (0–1, varsayılan) ya da `pixels` (TV ekran pikselleri, `/status`'taki boyut).
- `ttlMs`: kutular bu süre sonra kendiliğinden silinir (varsayılan 10000, `0` = bir sonraki isteğe kadar kalır).
- `bg` / `fg`: `#RRGGBB` ya da `#AARRGGBB`; verilmezse yarı saydam siyah üstüne beyaz yazı.
- Kısayol: `{"subtitle": "Merhaba"}` ekranın altına ortalanmış bir altyazı kutusu çizer.
- En fazla 64 kutu, gövde en fazla 256 KB.

Deneme:

```bash
curl -X POST http://192.168.1.50:8765/overlay -H "X-Token: <kod>" -H "Content-Type: application/json" \
  -d '{"subtitle":"Merhaba dünya"}'
```

Güvenlik: alıcı yalnızca açıkken dinler, kodsuz istekleri reddeder, düz HTTP kullanır. Yalnızca ev ağında kullanın.

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

## Diğer Android TV'lere yükleme

Onvo için yazılan adımlar diğer Google TV / Android TV cihazlarda da geçerlidir. Eski Android TV menülerinde
geliştirici modu **Ayarlar → Cihaz tercihleri → Hakkında → Yapı** satırından açılır. APK, USB bellek ve bir dosya
yöneticisiyle (ör. *File Commander*) ya da *Downloader* uygulamasıyla da kurulabilir.

## Kullanım (canlı altyazı modu)

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
