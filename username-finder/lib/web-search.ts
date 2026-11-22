import type {
  DuckDuckGoResult,
  SuggestedQuery,
  WebSearchLink,
  WebSearchPayload,
} from "./types";
import {
  buildIdentitySearchQuery,
  type ParsedPersonHints,
} from "./profile-hints";

function encodeQuery(q: string): string {
  return encodeURIComponent(q);
}

export function buildWebSearchPayload(
  username: string,
  hints: ParsedPersonHints | null
): Omit<WebSearchPayload, "duckDuckGoResults" | "duckDuckGoNote"> {
  const richQuery = buildIdentitySearchQuery(username, hints);

  const links: WebSearchLink[] = [
    {
      engine: "google",
      label: "Google",
      url: `https://www.google.com/search?q=${encodeQuery(richQuery)}`,
    },
    {
      engine: "bing",
      label: "Bing",
      url: `https://www.bing.com/search?q=${encodeQuery(richQuery)}`,
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
  ];

  if (hints?.firstName && hints.lastName) {
    const nameQ = `"${hints.firstName} ${hints.lastName}" "${username}"`;
    suggested.push({
      label: `Ad + soyad + kullanıcı adı`,
      url: `https://www.google.com/search?q=${encodeQuery(nameQ)}`,
    });
  }

  if (hints?.birthYear && hints.locationTokens[0]) {
    suggested.push({
      label: `Doğum yılı + şehir`,
      url: `https://www.google.com/search?q=${encodeQuery(
        `"${username}" ${hints.birthYear} "${hints.locationTokens[0]}"`
      )}`,
    });
  }

  return { links, suggestedQueries: suggested };
}

export async function fetchDuckDuckGoLite(
  query: string
): Promise<{ results: DuckDuckGoResult[]; note?: string }> {
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
      signal: AbortSignal.timeout(12_000),
    });

    if (!res.ok) {
      return {
        results: [],
        note: "DuckDuckGo yanıt vermedi; Google/Bing bağlantılarını kullanın.",
      };
    }

    const html = await res.text();
    const results = parseDuckDuckGoHtml(html).slice(0, 10);
    if (results.length === 0) {
      return {
        results: [],
        note: "DuckDuckGo sonucu ayrıştırılamadı (sayfa yapısı değişmiş olabilir).",
      };
    }
    return {
      results,
      note: "Sonuçlar DuckDuckGo HTML üzerinden alındı (ücretsiz, resmi olmayan).",
    };
  } catch {
    return {
      results: [],
      note: "DuckDuckGo isteği başarısız; Google/Bing bağlantılarını kullanın.",
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
    if (results.length >= 10) break;
  }

  if (results.length === 0) {
    const fallback = html.matchAll(
      /<a[^>]+rel="nofollow"[^>]+class="result__url"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/gi
    );
    for (const match of fallback) {
      const href = decodeDuckUrl(match[1]);
      const title = stripTags(match[2]).trim() || href;
      results.push({ title, url: href });
      if (results.length >= 10) break;
    }
  }

  return results;
}

function stripTags(s: string): string {
  return s.replace(/<[^>]+>/g, "").replace(/\s+/g, " ");
}