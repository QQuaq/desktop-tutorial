import { anonymousUploadName } from "./http-guard";
import type { ImageHit } from "./types";

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36";

const BLOCKED_DOMAINS = new Set([
  "yastatic.net",
  "yandex.com",
  "yandex.ru",
  "yandex.net",
  "bing.com",
  "microsoft.com",
  "passport.yandex.com",
  "mc.yandex.com",
]);

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function isUsefulDomain(domain: string): boolean {
  if (!domain || BLOCKED_DOMAINS.has(domain)) return false;
  for (const b of BLOCKED_DOMAINS) {
    if (domain.endsWith("." + b) || domain.includes(b)) return false;
  }
  return true;
}

function siteNameFromDomain(domain: string): string {
  const map: Record<string, string> = {
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "twitter.com": "X (Twitter)",
    "x.com": "X (Twitter)",
    "vk.com": "VK",
    "tiktok.com": "TikTok",
    "pinterest.com": "Pinterest",
    "reddit.com": "Reddit",
    "linkedin.com": "LinkedIn",
    "github.com": "GitHub",
  };
  for (const [k, v] of Object.entries(map)) {
    if (domain === k || domain.endsWith("." + k)) return v;
  }
  return domain;
}

function pushHit(
  list: ImageHit[],
  partial: Omit<ImageHit, "domain" | "siteName"> & { pageUrl: string }
) {
  const domain = hostname(partial.pageUrl);
  if (!isUsefulDomain(domain)) {
    return;
  }
  list.push({
    ...partial,
    domain,
    siteName: siteNameFromDomain(domain),
  });
}

function parseBingImageHtml(html: string, engine: string): ImageHit[] {
  const hits: ImageHit[] = [];
  for (const m of html.matchAll(
    /"murl":"(https?:[^"]+)".*?"purl":"(https?:[^"]+)".*?"t":"([^"]*)"/g
  )) {
    pushHit(hits, {
      engine,
      pageUrl: m[2].replace(/\\u002f/g, "/"),
      imageUrl: m[1].replace(/\\u002f/g, "/"),
      title: m[3].replace(/\\u0027/g, "'"),
      matchKind: "benzer_görsel",
      confidence: 72,
    });
  }
  if (hits.length === 0) {
    for (const m of html.matchAll(
      /"purl":"(https?:[^"]+)".*?"t":"([^"]*)"/g
    )) {
      pushHit(hits, {
        engine,
        pageUrl: m[1].replace(/\\u002f/g, "/"),
        title: m[2],
        matchKind: "ilgili_sayfa",
        confidence: 55,
      });
      if (hits.length >= 12) break;
    }
  }
  return hits;
}

function parseLoosePageLinks(html: string, engine: string): ImageHit[] {
  const hits: ImageHit[] = [];
  const seen = new Set<string>();
  for (const m of html.matchAll(/href="(https?:\/\/[^"]+)"/gi)) {
    let url = m[1].replace(/&amp;/g, "&");
    if (url.includes("yandex.") || url.includes("bing.com")) continue;
    const d = hostname(url);
    if (!d || seen.has(url)) continue;
    if (!/\.(com|net|org|io|ru|tr|de|fr)\b/i.test(d)) continue;
    seen.add(url);
    pushHit(hits, {
      engine,
      pageUrl: url,
      matchKind: "ilgili_sayfa",
      confidence: 40,
    });
    if (hits.length >= 8) break;
  }
  return hits;
}

async function fetchYandexMultipart(
  buffer: Buffer,
  mimeType: string
): Promise<{ hits: ImageHit[]; note: string }> {
  const filename = anonymousUploadName(mimeType);
  const form = new FormData();
  form.append(
    "upfile",
    new Blob([new Uint8Array(buffer)], { type: mimeType }),
    filename
  );
  const res = await fetch("https://yandex.com/images/search", {
    method: "POST",
    headers: { "User-Agent": UA },
    body: form,
    signal: AbortSignal.timeout(22_000),
  });
  if (!res.ok) {
    return { hits: [], note: "Yandex görsel yüklemesi yanıt vermedi." };
  }
  const html = await res.text();
  if (/captcha|робот|robot/i.test(html)) {
    return {
      hits: [],
      note: "Yandex captcha verdi; alttaki Yandex Görsel bağlantısını kullanın.",
    };
  }
  const hits: ImageHit[] = [];
  for (const m of html.matchAll(
    /"originPageUrl":"((?:https?:)?(?:\\\/|\/)[^"]+)"/g
  )) {
    const raw = m[1].replace(/\\\//g, "/");
    const pageUrl = raw.startsWith("http") ? raw : `https:${raw}`;
    pushHit(hits, {
      engine: "Yandex Görsel",
      pageUrl,
      matchKind: "aynı_görsel",
      confidence: 78,
    });
    if (hits.length >= 12) break;
  }
  if (hits.length === 0) {
    hits.push(...parseLoosePageLinks(html, "Yandex Görsel"));
  }
  return {
    hits,
    note:
      hits.length > 0
        ? "Yandex: fotoğraf doğrudan gönderildi (anonim dosya adı)."
        : "Yandex HTML sonucu boş olabilir (sayfa JS ile yüklenir).",
  };
}

async function fetchBingMultipart(
  buffer: Buffer,
  mimeType: string
): Promise<{ hits: ImageHit[]; note: string }> {
  const filename = anonymousUploadName(mimeType);
  const form = new FormData();
  form.append(
    "imgurl",
    new Blob([new Uint8Array(buffer)], { type: mimeType }),
    filename
  );
  const res = await fetch(
    "https://www.bing.com/images/api/search/upload?FORM=SECIMG",
    {
      method: "POST",
      headers: { "User-Agent": UA, Accept: "text/html,application/json" },
      body: form,
      signal: AbortSignal.timeout(20_000),
    }
  );
  if (!res.ok) {
    return { hits: [], note: "Bing görsel yüklemesi yanıt vermedi." };
  }
  const text = await res.text();
  let hits = parseBingImageHtml(text, "Bing Görsel");
  if (hits.length === 0) {
    hits.push(...parseLoosePageLinks(text, "Bing Görsel"));
  }
  return {
    hits,
    note:
      hits.length > 0
        ? "Bing: fotoğraf doğrudan gönderildi (anonim dosya adı)."
        : "Bing sonuç boş; alttaki Bing bağlantısını deneyin.",
  };
}

function dedupeAndRank(hits: ImageHit[]): ImageHit[] {
  const map = new Map<string, ImageHit>();
  for (const h of hits) {
    const key = h.pageUrl.split("#")[0];
    const prev = map.get(key);
    if (!prev || h.confidence > prev.confidence) {
      const engines = prev ? 1 : 0;
      map.set(key, {
        ...h,
        confidence: Math.min(95, h.confidence + engines * 8),
        matchKind:
          h.matchKind === "aynı_görsel" || prev?.matchKind === "aynı_görsel"
            ? "aynı_görsel"
            : h.matchKind,
      });
    } else if (prev) {
      map.set(key, {
        ...prev,
        confidence: Math.min(95, prev.confidence + 6),
      });
    }
  }
  return [...map.values()].sort((a, b) => b.confidence - a.confidence);
}

/**
 * Fotoğraf sunucuda saklanmaz; yalnızca arama motorlarına doğrudan yüklenir.
 * Herkese açık ara dosya barındırıcı kullanılmaz.
 */
export async function runReverseImageSearch(
  buffer: Buffer,
  mimeType: string
): Promise<{
  hits: ImageHit[];
  engineNotes: string[];
}> {
  const notes: string[] = [
    "Fotoğraf depolanmadı; yalnızca seçtiğiniz arama ile Yandex/Bing'e iletildi.",
  ];

  const [yandex, bing] = await Promise.all([
    fetchYandexMultipart(buffer, mimeType),
    fetchBingMultipart(buffer, mimeType),
  ]);

  const all = [...yandex.hits, ...bing.hits];
  notes.push(yandex.note);
  notes.push(bing.note);
  if (yandex.hits.length) notes.push(`Yandex: ${yandex.hits.length} kayıt.`);
  if (bing.hits.length) notes.push(`Bing: ${bing.hits.length} kayıt.`);

  return {
    hits: dedupeAndRank(all),
    engineNotes: notes,
  };
}