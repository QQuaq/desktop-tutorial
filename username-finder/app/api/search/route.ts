import {
  checkPlatforms,
  normalizeUsername,
} from "@/lib/check-profile";
import { platformsForMode } from "@/lib/platforms";
import {
  parsePersonHints,
  buildIdentitySearchQuery,
} from "@/lib/profile-hints";
import type {
  IdentityHighlight,
  PersonHintsInput,
  SearchMode,
  SearchResponse,
} from "@/lib/types";
import {
  buildWebSearchPayload,
  fetchDuckDuckGoLite,
} from "@/lib/web-search";

function jsonError(message: string, status: number) {
  return Response.json({ error: message }, { status });
}

function parsePerson(body: PersonHintsInput | undefined): PersonHintsInput | undefined {
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

export async function POST(request: Request) {
  let body: {
    username?: string;
    mode?: SearchMode;
    person?: PersonHintsInput;
  };
  try {
    body = await request.json();
  } catch {
    return jsonError("Geçersiz JSON.", 400);
  }

  const username = normalizeUsername(
    typeof body.username === "string" ? body.username : ""
  );
  if (!username) {
    return jsonError(
      "Geçersiz kullanıcı adı. 2–40 karakter; harf, rakam, nokta, alt çizgi veya tire kullanın.",
      400
    );
  }

  const person = parsePerson(body.person);
  const parsedHints = person ? parsePersonHints(person) : null;

  const mode: SearchMode =
    body.mode === "quick" && !parsedHints ? "quick" : "full";
  const platforms = platformsForMode(mode);
  const started = Date.now();

  const ddgQuery = buildIdentitySearchQuery(username, parsedHints);

  const [platformResults, ddg] = await Promise.all([
    checkPlatforms(platforms, username, parsedHints),
    fetchDuckDuckGoLite(ddgQuery),
  ]);

  const webBase = buildWebSearchPayload(username, parsedHints);
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
  identityHighlights.sort(
    (a, b) =>
      Number(b.strongMatch) - Number(a.strongMatch) ||
      b.matchedLabels.length - a.matchedLabels.length
  );

  const identityMatchCount = identityHighlights.length;
  const strongIdentityMatchCount = identityHighlights.filter(
    (h) => h.strongMatch
  ).length;

  const payload: SearchResponse = {
    username,
    mode,
    person,
    platforms: platformResults,
    webSearch: {
      ...webBase,
      duckDuckGoResults: ddg.results.length ? ddg.results : undefined,
      duckDuckGoNote: ddg.note,
    },
    identityHighlights,
    meta: {
      checkedCount: platformResults.length,
      foundCount,
      identityMatchCount,
      strongIdentityMatchCount,
      elapsedMs: Date.now() - started,
    },
  };

  return Response.json(payload);
}