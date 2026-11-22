import { buildProfileUrl } from "./platforms";
import type { CheckStatus, PlatformDef, PlatformResult } from "./types";

export const PER_SITE_TIMEOUT_MS = 8000;
export const CONCURRENCY_LIMIT = 10;

const USER_AGENT =
  "Mozilla/5.0 (compatible; UsernameFinder/1.0; +https://github.com/desktop-tutorial)";

function classify(
  platform: PlatformDef,
  httpStatus: number,
  bodySnippet: string
): CheckStatus {
  if (platform.notFoundStatus?.includes(httpStatus)) {
    return "not_found";
  }
  if (platform.forbiddenBodySubstrings?.length && bodySnippet) {
    const lower = bodySnippet.slice(0, 120_000).toLowerCase();
    for (const needle of platform.forbiddenBodySubstrings) {
      if (lower.includes(needle.toLowerCase())) {
        return "not_found";
      }
    }
  }
  if (platform.foundStatus.includes(httpStatus)) {
    return "found";
  }
  if (httpStatus >= 500) {
    return "error";
  }
  return "unknown";
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export async function checkOnePlatform(
  platform: PlatformDef,
  username: string
): Promise<PlatformResult> {
  const url = buildProfileUrl(platform.urlTemplate, username);
  const started = Date.now();

  try {
    const needsBody =
      platform.method === "GET" &&
      Boolean(platform.forbiddenBodySubstrings?.length);

    const response = await fetchWithTimeout(
      url,
      {
        method: platform.method,
        redirect: "follow",
        headers: {
          "User-Agent": USER_AGENT,
          Accept:
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
      },
      PER_SITE_TIMEOUT_MS
    );

    let bodySnippet = "";
    if (needsBody || platform.method === "GET") {
      try {
        const text = await response.text();
        bodySnippet = text.slice(0, 80_000);
      } catch {
        /* gövde okunamazsa yalnızca status */
      }
    }

    const httpStatus = response.status;
    const status = classify(platform, httpStatus, bodySnippet);

    return {
      platformId: platform.id,
      name: platform.name,
      category: platform.category,
      url,
      status,
      httpStatus,
      responseTimeMs: Date.now() - started,
    };
  } catch (err) {
    const message =
      err instanceof Error
        ? err.name === "AbortError"
          ? "Zaman aşımı"
          : err.message
        : "Bilinmeyen hata";
    return {
      platformId: platform.id,
      name: platform.name,
      category: platform.category,
      url,
      status: "error",
      responseTimeMs: Date.now() - started,
      error: message,
    };
  }
}

/** Basit eşzamanlılık havuzu. */
export async function checkPlatforms(
  platforms: PlatformDef[],
  username: string,
  onProgress?: (done: number, total: number) => void
): Promise<PlatformResult[]> {
  const results: PlatformResult[] = [];
  let index = 0;
  let done = 0;
  const total = platforms.length;

  async function worker() {
    while (index < platforms.length) {
      const i = index++;
      const platform = platforms[i];
      const result = await checkOnePlatform(platform, username);
      results[i] = result;
      done += 1;
      onProgress?.(done, total);
    }
  }

  const workers = Array.from(
    { length: Math.min(CONCURRENCY_LIMIT, platforms.length) },
    () => worker()
  );
  await Promise.all(workers);
  return results;
}

export const USERNAME_PATTERN = /^[a-zA-Z0-9._-]{2,40}$/;

export function normalizeUsername(raw: string): string | null {
  const trimmed = raw.trim().replace(/^@/, "");
  if (!USERNAME_PATTERN.test(trimmed)) return null;
  return trimmed;
}