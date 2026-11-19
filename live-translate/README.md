# Canlı İngilizce → Türkçe altyazı

Mikrofondan İngilizce konuşma tanır; Türkçe altyazı ve isteğe bağlı sesli okuma.

## Ev ağında PC sunucusu (GitHub yok)

Windows’ta `live-translate` klasöründe **`sunucu.bat`** dosyasına çift tıkla.

Mac/Linux:

```bash
chmod +x sunucu.sh && ./sunucu.sh
```

Tarayıcıda aç:

- **Bu bilgisayarda mikrofon için:** `http://127.0.0.1:3456`
- **Telefon / başka cihaz (aynı Wi‑Fi):** terminalde yazan `http://192.168.x.x:3456` adresi

Sunucuyu kapatmak: siyah pencerede **Ctrl+C**.

### Mikrofon notu

Chrome/Edge, mikrofonu çoğu zaman yalnızca **127.0.0.1** veya **HTTPS** üzerinde açar. Telefondan `http://192.168...` ile mikrofon çalışmazsa çeviriyi **sunucu PC’de** `127.0.0.1:3456` üzerinden kullan.

### Geliştirici

```bash
npm install
npm run dev          # sadece bu PC
npm run dev:lan      # ağdan da erişim (geliştirme)
npm run serve:lan    # derle + ağda yayın
```

## Teknik

- Next.js, port **3456**, dinleme adresi **0.0.0.0** (sadece yerel ağ; internete açma).
- Çeviri: tarayıcıdan MyMemory API (internet gerekir; sunucu dışarıya sadece çeviri isteği atar).