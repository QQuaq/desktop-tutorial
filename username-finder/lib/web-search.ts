import type { SuggestedQuery, WebSearchLink, WebSearchPayload } from "./types";
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
): Pick<WebSearchPayload, "links" | "suggestedQueries"> {
  const richQuery = buildIdentitySearchQuery(username, hints);

  const links: WebSearchLink[] = [
    {
      engine: "google",
      label: "Google",
      url: `https://www.google.com/search?q=${encodeQuery(richQuery)}`,
    },
    {
      engine: "yandex",
      label: "Yandex",
      url: `https://yandex.com/search/?text=${encodeQuery(richQuery)}`,
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
      label: `Yandex — kullanıcı adı`,
      url: `https://yandex.com/search/?text=${encodeQuery(`"${username}"`)}`,
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
    suggested.push({
      label: `Yandex — ad soyad`,
      url: `https://yandex.com/search/?text=${encodeQuery(nameQ)}`,
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