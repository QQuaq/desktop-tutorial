import { parseUsernameList } from "@/lib/check-profile";
import { parsePersonHints } from "@/lib/profile-hints";
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

  const parsed = parseUsernameList(body.username, body.usernames);
  if (!parsed.ok) return jsonError(parsed.error, 400);

  const person = personFromBody(body.person);
  const parsedHints = person ? parsePersonHints(person) : null;
  const mode: SearchMode =
    body.mode === "quick" && !parsedHints ? "quick" : "full";

  const batchStarted = Date.now();
  const items: SearchResponse[] = [];

  for (const name of parsed.names) {
    items.push(
      await runUsernameSearch(name, parsedHints, person, mode)
    );
  }

  if (items.length === 1) {
    return Response.json(items[0]);
  }

  const payload: BatchSearchResponse = {
    batch: true,
    person,
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