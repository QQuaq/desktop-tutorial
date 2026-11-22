import { hostImageTemporarily } from "./image-host";
import type { ImageHit, ImageMatchKind } from "./types";

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36";

const BLOCKED_DOMAINS = new Set([
  "yastatic.net",
  "yandex.com",
  "yandex.ru",
  "yandex.net",
  "bing.com",
  "microsoft.com",
  "tmpfiles.org",
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

async function fetchBingByImageUrl(publicUrl: string): Promise<ImageHit[]> {
  const q = encodeURIComponent(`imgurl:${publicUrl}`);
  const url = `https://www.bing.com/images/search?q=${q}&FORM=IRIBIP`;
  const res = await fetch(url, {
    headers: { "User-Agent": UA, Accept: "text/html" },
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) return [];
  const html = await res.text();
  return parseBingImageHtml(html, "Bing Görsel");
}

async function fetchYandexByImageUrl(publicUrl: string): Promise<{
  hits: ImageHit[];
  note: string;
}> {
  const searchUrl = `https://yandex.com/images/search?rpt=imageview&url=${encodeURIComponent(publicUrl)}`;
  const res = await fetch(searchUrl, {
    headers: { "User-Agent": UA, "Accept-Language": "tr,en" },
    signal: AbortSignal.timeout(18_000),
  });
  if (!res.ok) {
    return { hits: [], note: "Yandex görsel araması yanıt vermedi." };
  }
  const html = await res.text();
  if (/captcha|робот|robot/i.test(html)) {
    return {
      hits: [],
      note: "Yandex captcha verdi; telefonda Yandex Görsel ile yükleyin.",
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
        ? "Yandex tersine görsel araması tamamlandı."
        : "Yandex HTML sonucu boş (sayfa JS ile yükleniyor olabilir).",
  };
}

async function fetchYandexMultipart(
  buffer: Buffer,
  filename: string
): Promise<ImageHit[]> {
  const form = new FormData();
  form.append(
    "upfile",
    new Blob([new Uint8Array(buffer)], { type: "image/jpeg" }),
    filename
  );
  const res = await fetch("https://yandex.com/images/search", {
    method: "POST",
    headers: { "User-Agent": UA },
    body: form,
    signal: AbortSignal.timeout(20_000),
  });
  if (!res.ok) return [];
  const html = await res.text();
  return parseLoosePageLinks(html, "Yandex (yükleme)");
}

async function fetchSerpApiLens(publicUrl: string): Promise<ImageHit[]> {
  const key = process.env.SERPAPI_API_KEY?.trim();
  if (!key) return [];
  const params = new URLSearchParams({
    engine: "google_lens",
    url: publicUrl,
    api_key: key,
  });
  const res = await fetch(`https://serpapi.com/search.json?${params}`, {
    signal: AbortSignal.timeout(20_000),
  });
  if (!res.ok) return [];
  const json = (await res.json()) as {
    visual_matches?: { title?: string; link?: string; source?: string }[];
    knowledge_graph?: { title?: string; website?: string };
  };
  const hits: ImageHit[] = [];
  for (const m of json.visual_matches ?? []) {
    if (!m.link) continue;
    pushHit(hits, {
      engine: "Google Lens (API)",
      pageUrl: m.link,
      title: m.title,
      matchKind: "benzer_görsel",
      confidence: 85,
      snippet: m.source,
    });
    if (hits.length >= 10) break;
  }
  return hits;
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

export async function runReverseImageSearch(
  buffer: Buffer,
  filename: string,
  mimeType: string
): Promise<{
  hits: ImageHit[];
  engineNotes: string[];
  tempImageUrl?: string;
}> {
  const notes: string[] = [];
  const all: ImageHit[] = [];

  const hosted = await hostImageTemporarily(buffer, filename, mimeType);
  if ("error" in hosted) {
    notes.push(hosted.error);
    const yandexDirect = await fetchYandexMultipart(buffer, filename);
    all.push(...yandexDirect);
    if (yandexDirect.length) {
      notes.push("Yandex doğrudan yükleme ile sonuç alındı.");
    }
    return { hits: dedupeAndRank(all), engineNotes: notes };
  }

  const publicUrl = hosted.url;
  notes.push("Görsel geçici URL ile motorlara gönderildi (~1 saat).");

  const [bing, yandex, serp, yandexUp] = await Promise.all([
    fetchBingByImageUrl(publicUrl),
    fetchYandexByImageUrl(publicUrl),
    fetchSerpApiLens(publicUrl),
    fetchYandexMultipart(buffer, filename),
  ]);

  all.push(...bing, ...yandex.hits, ...serp, ...yandexUp);
  notes.push(yandex.note);
  if (bing.length) notes.push(`Bing: ${bing.length} sonuç.`);
  if (serp.length) notes.push(`Google Lens API: ${serp.length} sonuç.`);
  if (!process.env.SERPAPI_API_KEY) {
    notes.push(
      "İsteğe bağlı SERPAPI_API_KEY ile Google Lens sonuçları güçlendirilir."
    );
  }

  return {
    hits: dedupeAndRank(all),
    engineNotes: notes,
    tempImageUrl: publicUrl,
  };
}