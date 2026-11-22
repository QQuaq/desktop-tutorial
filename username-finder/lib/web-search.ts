import type { DuckDuckGoResult, SuggestedQuery, WebSearchLink, WebSearchPayload } from "./types";

function encodeQuery(q: string): string {
  return encodeURIComponent(q);
}

export function buildWebSearchPayload(username: string): Omit<WebSearchPayload, "duckDuckGoResults" | "duckDuckGoNote"> {
  const links: WebSearchLink[] = [
    {
      engine: "google",
      label: "Google",
      url: `https://www.google.com/search?q=${encodeQuery(username)}`,
    },
    {
      engine: "yandex",
      label: "Yandex",
      url: `https://yandex.com/search/?text=${encodeQuery(username)}`,
    },
    {
      engine: "bing",
      label: "Bing",
      url: `https://www.bing.com/search?q=${encodeQuery(username)}`,
    },
  ];

  const suggested: SuggestedQuery[] = [
    {
      label: `Tam kullanıcı adı: ${username}`,
      url: `https://www.google.com/search?q=${encodeQuery(`"${username}"`)}`,
    },
    {
      label: `Instagram'da: ${username}`,
      url: `https://www.google.com/search?q=${encodeQuery(`"${username}" site:instagram.com`)}`,
    },
    {
      label: `Twitter/X'te: ${username}`,
      url: `https://www.google.com/search?q=${encodeQuery(`"${username}" site:x.com OR site:twitter.com`)}`,
    },
    {
      label: `GitHub'da: ${username}`,
      url: `https://www.google.com/search?q=${encodeQuery(`"${username}" site:github.com`)}`,
    },
    {
      label: `Yandex — tırnaklı arama`,
      url: `https://yandex.com/search/?text=${encodeQuery(`"${username}"`)}`,
    },
  ];

  return { links, suggestedQueries: suggested };
}

/**
 * DuckDuckGo HTML sürümü (API anahtarı gerekmez; yapı değişebilir).
 * Yandex/Google HTML kazıması daha kırılgandır; kullanıcıya doğrudan link verilir.
 *
 * Gelecekte Yandex XML API için: YANDEX_SEARCH_API_KEY ve YANDEX_FOLDER_ID ortam değişkenleri.
 */
export async function fetchDuckDuckGoLite(
  username: string
): Promise<{ results: DuckDuckGoResult[]; note?: string }> {
  const query = `"${username}"`;
  const body = new URLSearchParams({ q: query });

  try {
    const res = await fetch("https://html.duckduckgo.com/html/", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent":
          "Mozilla/5.0 (compatible; UsernameFinder/1.0; DuckDuckGo HTML)",
      },
      body: body.toString(),
      signal: AbortSignal.timeout(10_000),
    });

    if (!res.ok) {
      return {
        results: [],
        note: "DuckDuckGo yanıt vermedi; yukarıdaki arama bağlantılarını kullanın.",
      };
    }

    const html = await res.text();
    const results = parseDuckDuckGoHtml(html).slice(0, 5);
    if (results.length === 0) {
      return {
        results: [],
        note: "DuckDuckGo sonucu ayrıştırılamadı (sayfa yapısı değişmiş olabilir).",
      };
    }
    return { results, note: "Sonuçlar DuckDuckGo HTML üzerinden alındı (ücretsiz, resmi olmayan)." };
  } catch {
    return {
      results: [],
      note: "DuckDuckGo isteği başarısız; Google/Yandex bağlantılarını kullanın.",
    };
  }
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

function parseDuckDuckGoHtml(html: string): DuckDuckGoResult[] {
  const results: DuckDuckGoResult[] = [];
  const resultBlock = html.matchAll(
    /<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi
  );

  for (const match of resultBlock) {
    const href = decodeDuckUrl(match[1]);
    const title = stripTags(match[2]).trim();
    if (!title || !href.startsWith("http")) continue;
    results.push({ title, url: href });
    if (results.length >= 5) break;
  }

  if (results.length === 0) {
    const fallback = html.matchAll(
      /<a[^>]+rel="nofollow"[^>]+class="result__url"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi
    );
    for (const match of fallback) {
      const href = decodeDuckUrl(match[1]);
      const title = stripTags(match[2]).trim() || href;
      results.push({ title, url: href });
      if (results.length >= 5) break;
    }
  }

  return results;
}

function stripTags(s: string): string {
  return s.replace(/<[^>]+>/g, "").replace(/\s+/g, " ");
}