import { parsePersonHints } from "@/lib/profile-hints";
import { resolveSearchUsernames } from "@/lib/username-derive";
import {
  personFromBody,
  runUsernameSearch,
} from "@/lib/search-run";
import type {
  BatchSearchResponse,
  PersonHintsInput,
  SearchMode,
  SearchResponse,
} from "@/lib/types";

function jsonError(message: string, status: number) {
  return Response.json({ error: message }, { status });
}

export async function POST(request: Request) {
  let body: {
    username?: string;
    usernames?: string[];
    mode?: SearchMode;
    person?: PersonHintsInput;
  };
  try {
    body = await request.json();
  } catch {
    return jsonError("Geçersiz JSON.", 400);
  }

  const person = personFromBody(body.person);

  const rawList: string[] = [];
  if (Array.isArray(body.usernames)) {
    for (const item of body.usernames) {
      if (typeof item === "string" && item.trim()) rawList.push(item.trim());
    }
  } else if (typeof body.username === "string" && body.username.trim()) {
    rawList.push(body.username.trim());
  }

  const resolved = resolveSearchUsernames(rawList, person);
  if (!resolved.ok) return jsonError(resolved.error, 400);
  const parsedHints = person ? parsePersonHints(person) : null;
  const mode: SearchMode =
    body.mode === "quick" && !parsedHints ? "quick" : "full";

  const batchStarted = Date.now();
  const items: SearchResponse[] = [];

  for (const name of resolved.names) {
    const result = await runUsernameSearch(name, parsedHints, person, mode);
    items.push({
      ...result,
      generatedFromName: resolved.derivedFromName.includes(name),
    });
  }

  if (items.length === 1) {
    const one = items[0];
    return Response.json({
      ...one,
      derivedFromName:
        resolved.derivedFromName.length > 0
          ? resolved.derivedFromName
          : undefined,
    });
  }

  const payload: BatchSearchResponse = {
    batch: true,
    person,
    derivedFromName:
      resolved.derivedFromName.length > 0
        ? resolved.derivedFromName
        : undefined,
    items,
    meta: {
      usernameCount: items.length,
      totalElapsedMs: Date.now() - batchStarted,
      totalFound: items.reduce((n, i) => n + i.meta.foundCount, 0),
      totalStrongIdentity: items.reduce(
        (n, i) => n + i.meta.strongIdentityMatchCount,
        0
      ),
    },
  };

  return Response.json(payload);
}