import {
  checkPlatforms,
  normalizeUsername,
} from "@/lib/check-profile";
import { platformsForMode } from "@/lib/platforms";
import type { SearchMode, SearchResponse } from "@/lib/types";
import {
  buildWebSearchPayload,
  fetchDuckDuckGoLite,
} from "@/lib/web-search";

function jsonError(message: string, status: number) {
  return Response.json({ error: message }, { status });
}

export async function POST(request: Request) {
  let body: { username?: string; mode?: SearchMode };
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

  const mode: SearchMode = body.mode === "full" ? "full" : "quick";
  const platforms = platformsForMode(mode);
  const started = Date.now();

  const [platformResults, ddg] = await Promise.all([
    checkPlatforms(platforms, username),
    fetchDuckDuckGoLite(username),
  ]);

  const webBase = buildWebSearchPayload(username);
  const foundCount = platformResults.filter((r) => r.status === "found").length;

  const payload: SearchResponse = {
    username,
    mode,
    platforms: platformResults,
    webSearch: {
      ...webBase,
      duckDuckGoResults: ddg.results.length ? ddg.results : undefined,
      duckDuckGoNote: ddg.note,
    },
    meta: {
      checkedCount: platformResults.length,
      foundCount,
      elapsedMs: Date.now() - started,
    },
  };

  return Response.json(payload);
}