# Kullanıcı adı arama (username-finder)

Türkçe arayüzlü, **detaylı kullanıcı adı bulucu**: Bir takma adı birçok sosyal/medya/geliştirici platformunda herkese açık profil URL kalıplarıyla kontrol eder; Google, Yandex ve DuckDuckGo için arama bağlantıları (ve mümkünse DuckDuckGo HTML özeti) sunar.

## Yerel geliştirme

```bash
cd username-finder
npm install
npm run dev
```

Tarayıcı: [http://127.0.0.1:3457](http://127.0.0.1:3457)

Diğer komutlar: `npm run build`, `npm run start`, ağ üzerinden `npm run dev:lan` / `npm run start:lan`.

## Özellikler

- **Hızlı mod**: Sık kullanılan ~15 platform.
- **Detaylı mod**: Kayıtlı tüm platformlar (forum, oyun, kod, vb.).
- `POST /api/search` — gövde: `{ "username": "...", "mode": "quick" | "full" }`
- Web araması: Google ve Yandex doğrudan bağlantılar; önerilen `site:` sorguları; DuckDuckGo HTML (API anahtarı yok).

## Doğrulama mantığı (sınırlamalar)

Her platform `lib/platforms.ts` içinde tanımlıdır:

- `HEAD` veya `GET`, beklenen HTTP kodları, isteğe bağlı gövdede “bulunamadı” alt dizgileri.
- Siteler bot koruması, soft 404 veya özel kullanıcı kimliği (ör. yalnızca sayısal ID) kullanabilir → **yanlış pozitif/negatif** ve `unknown`/`error` mümkündür.
- Giriş, özel mesaj veya özel OSINT yok; yalnızca bilinen herkese açık URL şablonları.

## Hukuki ve etik not

Bu araç yalnızca herkese açık profil sayfalarına HTTP isteği gönderir. Sonuçlar kesin kimlik tespiti sağlamaz. Taciz, stalking veya hizmet şartlarını ihlal eden kullanım sorumluluğu kullanıcıdadır.

## Gelecekte Yandex XML API

Ücretli/resmi Yandex arama entegrasyonu için genelde şunlar gerekir (şu an **kullanılmıyor**):

- `YANDEX_SEARCH_API_KEY` — Yandex Cloud Search API anahtarı
- `YANDEX_FOLDER_ID` — Cloud klasör kimliği

DuckDuckGo HTML ve manuel Google/Yandex bağlantıları API anahtarı gerektirmez.

## Proje yapısı

`live-translate/` ile aynı aileden Next.js 15 App Router + TypeScript. Bu klasör `live-translate` ile kardeştir; monorepo kökünde ayrı `package.json` vardır.