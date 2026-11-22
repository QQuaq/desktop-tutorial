import { checkPlatforms } from "@/lib/check-profile";
import { scanSearchEngines } from "@/lib/engine-search";
import { buildImageSearchOffers } from "@/lib/image-search";
import { platformsForMode } from "@/lib/platforms";
import {
  parsePersonHints,
  buildIdentitySearchQuery,
  type ParsedPersonHints,
} from "@/lib/profile-hints";
import type {
  IdentityHighlight,
  PersonHintsInput,
  SearchMode,
  SearchResponse,
} from "@/lib/types";
import { buildWebSearchPayload } from "@/lib/web-search";

export async function runUsernameSearch(
  username: string,
  parsedHints: ParsedPersonHints | null,
  person: PersonHintsInput | undefined,
  mode: SearchMode
): Promise<SearchResponse> {
  const effectiveMode: SearchMode =
    mode === "quick" && !parsedHints ? "quick" : "full";
  const platforms = platformsForMode(effectiveMode);
  const started = Date.now();
  const searchQuery = buildIdentitySearchQuery(username, parsedHints);

  const [platformResults, engineScans] = await Promise.all([
    checkPlatforms(platforms, username, parsedHints),
    scanSearchEngines(searchQuery, username, parsedHints),
  ]);

  const webBase = buildWebSearchPayload(username, parsedHints);
  const imageSearch = buildImageSearchOffers(username, parsedHints);
  const foundCount = platformResults.filter((r) => r.status === "found").length;

  const identityHighlights: IdentityHighlight[] = [];
  for (const p of platformResults) {
    if (!p.identity || p.identity.matchedCount === 0) continue;
    if (p.status !== "found" && p.status !== "unknown") continue;
    identityHighlights.push({
      platformName: p.name,
      url: p.url,
      summary: p.identity.summary,
      strongMatch: p.identity.strongMatch,
      matchedLabels: p.identity.fields
        .filter((f) => f.matched)
        .map((f) => f.label),
    });
  }

  for (const scan of engineScans) {
    for (const hit of scan.results) {
      if (!hit.identityMatch || hit.identityMatch.matchedLabels.length === 0) {
        continue;
      }
      identityHighlights.push({
        platformName: `${scan.label} sonucu`,
        url: hit.url,
        summary: hit.identityMatch.summary,
        strongMatch: hit.identityMatch.strongMatch,
        matchedLabels: hit.identityMatch.matchedLabels,
      });
    }
  }

  identityHighlights.sort(
    (a, b) =>
      Number(b.strongMatch) - Number(a.strongMatch) ||
      b.matchedLabels.length - a.matchedLabels.length
  );

  const engineHitCount = engineScans.reduce((n, s) => n + s.results.length, 0);
  const ddg = engineScans.find((s) => s.engine === "duckduckgo");

  return {
    username,
    mode: effectiveMode,
    person,
    platforms: platformResults,
    webSearch: {
      ...webBase,
      engineScans,
      imageSearch,
      duckDuckGoResults: ddg?.results,
      duckDuckGoNote: ddg?.note,
    },
    identityHighlights,
    meta: {
      checkedCount: platformResults.length,
      foundCount,
      identityMatchCount: identityHighlights.length,
      strongIdentityMatchCount: identityHighlights.filter((h) => h.strongMatch)
        .length,
      engineHitCount,
      elapsedMs: Date.now() - started,
    },
  };
}

export function personFromBody(
  body: PersonHintsInput | undefined
): PersonHintsInput | undefined {
  if (!body || typeof body !== "object") return undefined;
  const person: PersonHintsInput = {};
  for (const key of ["firstName", "lastName", "birthDate", "location"] as const) {
    const v = body[key];
    if (typeof v === "string" && v.trim()) {
      person[key] = v.trim();
    }
  }
  return Object.keys(person).length ? person : undefined;
}