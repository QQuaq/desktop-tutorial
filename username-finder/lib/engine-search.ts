import {
  analyzePageIdentity,
  type ParsedPersonHints,
} from "./profile-hints";
import type { EngineScan, WebHit } from "./types";

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

function stripTags(s: string): string {
  return s.replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
}

function enrichHits(
  hits: WebHit[],
  username: string,
  hints: ParsedPersonHints | null
): WebHit[] {
  if (!hints) return hits;
  return hits.map((h) => {
    const id = analyzePageIdentity(
      `${h.title} ${h.snippet ?? ""}`,
      username,
      hints
    );
    if (id.matchedCount === 0) return h;
    return {
      ...h,
      identityMatch: {
        matchedLabels: id.fields.filter((f) => f.matched).map((f) => f.label),
        strongMatch: id.strongMatch,
        summary: id.summary,
      },
    };
  });
}

export async function fetchDuckDuckGoHits(query: string): Promise<WebHit[]> {
  const body = new URLSearchParams({ q: query });
  const res = await fetch("https://html.duckduckgo.com/html/", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "User-Agent": "Mozilla/5.0 (compatible; UsernameFinder/1.1)",
    },
    body: body.toString(),
    signal: AbortSignal.timeout(12_000),
  });
  if (!res.ok) return [];
  const html = await res.text();
  const results: WebHit[] = [];

  for (const match of html.matchAll(
    /<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi
  )) {
    const href = decodeDuckUrl(match[1]);
    const title = stripTags(match[2]);
    if (!title || !href.startsWith("http")) continue;
    results.push({ title, url: href });
    if (results.length >= 8) break;
  }
  return results;
}

function decodeDuckUrl(href: string): string {
  try {
    if (href.includes("uddg=")) {
      const u = new URL(href, "https://duckduckgo.com");
      const inner = u.searchParams.get("uddg");
      if (inner) return decodeURIComponent(inner);
    }
    return href;
  } catch {
    return href;
  }
}

export async function fetchBingHits(query: string): Promise<WebHit[]> {
  const url = `https://www.bing.com/search?q=${encodeURIComponent(query)}&setlang=tr`;
  const res = await fetch(url, {
    headers: { "User-Agent": UA, Accept: "text/html" },
    signal: AbortSignal.timeout(12_000),
  });
  if (!res.ok) return [];
  const html = await res.text();
  const results: WebHit[] = [];

  for (const block of html.matchAll(
    /<li class="b_algo"[\s\S]*?<h2>\s*<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi
  )) {
    const href = block[1].replace(/&amp;/g, "&");
    const title = stripTags(block[2]);
    if (!title || !href.startsWith("http")) continue;
    let snippet = "";
    const after = block[0];
    const pMatch = after.match(/<p[^>]*>([\s\S]*?)<\/p>/i);
    if (pMatch) snippet = stripTags(pMatch[1]);
    results.push({ title, url: href, snippet });
    if (results.length >= 8) break;
  }
  return results;
}

/** Yandex çoğu sunucuda captcha verir; sonuç boş olabilir. */
export async function fetchYandexHits(query: string): Promise<{
  hits: WebHit[];
  blocked: boolean;
}> {
  const url = `https://yandex.com/search/?text=${encodeURIComponent(query)}&lr=11508`;
  const res = await fetch(url, {
    headers: {
      "User-Agent": UA,
      Accept: "text/html",
      "Accept-Language": "tr,en;q=0.8",
    },
    signal: AbortSignal.timeout(12_000),
  });
  const html = res.ok ? await res.text() : "";
  if (
    !html ||
    /captcha|Вы не робот|aren't a robot/i.test(html) ||
    html.length < 500
  ) {
    return { hits: [], blocked: true };
  }

  const results: WebHit[] = [];
  for (const match of html.matchAll(
    /<a[^>]+(?:class="[^"]*organic[^"]*"|data-bem)[^>]*href="(https?:\/\/[^"]+)"[^>]*>([\s\S]*?)<\/a>/gi
  )) {
    const title = stripTags(match[2]);
    const href = match[1];
    if (title.length < 2 || href.includes("yandex.")) continue;
    results.push({ title, url: href });
    if (results.length >= 8) break;
  }

  return { hits: results, blocked: results.length === 0 };
}

export async function scanSearchEngines(
  query: string,
  username: string,
  hints: ParsedPersonHints | null
): Promise<EngineScan[]> {
  const [ddg, bing, yandex] = await Promise.all([
    fetchDuckDuckGoHits(query).catch(() => []),
    fetchBingHits(query).catch(() => []),
    fetchYandexHits(query).catch(() => ({ hits: [], blocked: true })),
  ]);

  const scans: EngineScan[] = [
    {
      engine: "duckduckgo",
      label: "DuckDuckGo",
      results: enrichHits(ddg, username, hints),
      status: ddg.length ? "ok" : "empty",
      note:
        ddg.length === 0
          ? "DuckDuckGo sonuç döndürmedi."
          : "Sunucu tarafı metin araması.",
    },
    {
      engine: "bing",
      label: "Bing",
      results: enrichHits(bing, username, hints),
      status: bing.length ? "ok" : "empty",
      note:
        bing.length === 0
          ? "Bing sonuç döndürmedi veya HTML yapısı değişti."
          : "Sunucu tarafı metin araması.",
    },
    {
      engine: "yandex",
      label: "Yandex",
      results: enrichHits(yandex.hits, username, hints),
      status: yandex.hits.length ? "ok" : yandex.blocked ? "blocked" : "empty",
      note: yandex.hits.length
        ? "Sunucu tarafı Yandex metin araması."
        : yandex.blocked
          ? "Yandex sunucuyu bot olarak gördü (captcha). Aşağıdaki Yandex metin/görsel bağlantılarından telefonda arayın."
          : "Yandex sonuç bulamadı.",
    },
  ];

  return scans;
}