# Canlı İngilizce → Türkçe altyazı

Mikrofondan İngilizce konuşma tanır; Türkçe altyazı ve isteğe bağlı sesli okuma.

## GitHub Pages adresi

**https://qquaq.github.io/desktop-tutorial/**

(Şahsen açmayı dene; sonunda `/` olsun.)

## 404 alıyorsan (bir kez ayarla)

1. [Repository → Settings → Pages](https://github.com/QQuaq/desktop-tutorial/settings/pages)
2. **Build and deployment** → **Deploy from a branch**
3. Branch: **`main`**, klasör: **`/docs`**
4. **Save** — yayın 1–3 dakika sürebilir

`main` dalına kod gidince GitHub Actions `docs/` klasörünü otomatik günceller.

### Repo private ise

Private repolarda **ücretsiz** hesapta GitHub Pages genelde **dışarıya kapalı** veya **404** verir. Çözümler:

- Repoyu **public** yap, veya
- GitHub planında private Pages aç, veya
- [Cursor’daki yayın](https://ingilizce-turkce.apps.grok.bot) adresini kullan

## Yerel geliştirme

```bash
npm install
npm run dev
```

http://127.0.0.1:3456

## GitHub Pages derlemesi (lokal)

```bash
npm run build:gh-pages
```

Çıktı: `out/` → üretimde `docs/` içine kopyalanır.