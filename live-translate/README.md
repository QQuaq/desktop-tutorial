# Canlı İngilizce → Türkçe altyazı

Mikrofondan İngilizce konuşma tanır; Türkçe altyazı ve isteğe bağlı sesli okuma.

## GitHub Pages

`main` dalına push sonrası workflow otomatik yayınlar:

**https://qquaq.github.io/desktop-tutorial/**

İlk kez: GitHub repo → Settings → Pages → **Build and deployment** → Source: **GitHub Actions**.

## Yerel geliştirme

```bash
npm install
npm run dev
```

Tarayıcı: http://127.0.0.1:3456

## GitHub Pages yerel derleme

```bash
npm run build:gh-pages
```

Çıktı: `out/` klasörü.