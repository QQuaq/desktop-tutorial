# Canlı İngilizce → Türkçe altyazı

Mikrofondan İngilizce konuşma tanır; Türkçe altyazı ve isteğe bağlı sesli okuma.

## GitHub Pages

`main` dalına push sonrası workflow otomatik yayınlar:

**https://qquaq.github.io/desktop-tutorial/**

İlk kez (bir kez yapman yeter): GitHub repo → **Settings** → **Pages** → kaynak olarak **`gh-pages`** dalı, klasör **`/ (root)`**. (Alternatif: kaynak **GitHub Actions**; o zaman workflow’un en üstündeki deploy-pages adımını kullan.)

Repo **private** ise GitHub’da Pages için ek plan/izin gerekebilir; site açılmıyorsa repo’yu public yap veya Settings’ten Pages görünürlüğünü kontrol et.

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