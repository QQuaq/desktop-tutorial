import type { ImageSearchOffer } from "./types";
import { buildIdentitySearchQuery, type ParsedPersonHints } from "./profile-hints";

const encode = (q: string) => encodeURIComponent(q);

export function buildImageSearchOffers(
  username: string,
  hints: ParsedPersonHints | null
): ImageSearchOffer[] {
  const textQ = buildIdentitySearchQuery(username, hints);

  return [
    {
      engine: "yandex-images",
      label: "Yandex Görsel (metin)",
      url: `https://yandex.com/images/search?text=${encode(textQ)}`,
      mode: "text",
      note: "Kullanıcı adı ve kimlik bilgileriyle ilişkili görseller.",
    },
    {
      engine: "yandex-images-upload",
      label: "Yandex Görsel (fotoğraf yükle)",
      url: "https://yandex.com/images/",
      mode: "upload",
      note: "Siteyi açıp kamera veya «yükle» ile profil fotoğrafını seçin; benzer yüzleri arar.",
    },
    {
      engine: "google-lens",
      label: "Google Lens",
      url: "https://lens.google.com/",
      mode: "upload",
      note: "Telefonda fotoğraf yükleyerek tersine görsel arama.",
    },
    {
      engine: "bing-visual",
      label: "Bing Görsel arama",
      url: `https://www.bing.com/images/search?q=${encode(textQ)}&form=HDRSC2`,
      mode: "text",
      note: "Metinle görsel arama; görsel yükleme için arama kutusundaki kamera ikonu.",
    },
  ];
}

export const MAX_IMAGE_BYTES = 1_500_000;

/** Yalnızca boyut doğrulama; görsel sunucuda saklanmaz. */
export function validateImagePayload(
  mimeType: string | undefined,
  byteLength: number
): string | null {
  if (byteLength <= 0) return "Boş dosya.";
  if (byteLength > MAX_IMAGE_BYTES) return "Dosya en fazla ~1,5 MB olabilir.";
  if (!mimeType?.startsWith("image/")) return "Yalnızca resim dosyası.";
  return null;
}