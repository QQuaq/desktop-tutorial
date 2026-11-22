import { getIdentity } from "../cursor/identity";

type Bucket = { count: number; resetAt: number };

const buckets = new Map<string, Bucket>();

function clientKey(request: Request, route: string): string {
  const forwarded = request.headers.get("x-forwarded-for");
  const ip = forwarded?.split(",")[0]?.trim() || "unknown";
  return `${route}:${ip}`;
}

async function identityKey(request: Request, route: string): Promise<string> {
  const id = await getIdentity(request);
  if (id.verified && id.sub) {
    return `${route}:user:${id.sub}`;
  }
  return clientKey(request, route);
}

function takeToken(key: string, limit: number, windowMs: number): boolean {
  const now = Date.now();
  let b = buckets.get(key);
  if (!b || now >= b.resetAt) {
    b = { count: 0, resetAt: now + windowMs };
    buckets.set(key, b);
  }
  if (b.count >= limit) return false;
  b.count += 1;
  return true;
}

export async function requireSignedInViewer(
  request: Request
): Promise<{ ok: true } | { ok: false; response: Response }> {
  const id = await getIdentity(request);
  if (!id.verified) {
    return {
      ok: false,
      response: Response.json(
        {
          error:
            "Bu uygulamayı Cursor ile açmanız gerekir; oturum doğrulanamadı.",
          reason: id.reason,
        },
        { status: 401 }
      ),
    };
  }
  return { ok: true };
}

export async function enforceRateLimit(
  request: Request,
  route: string,
  limit: number,
  windowMs: number
): Promise<Response | null> {
  const key = await identityKey(request, route);
  if (!takeToken(key, limit, windowMs)) {
    return Response.json(
      {
        error: "Çok fazla istek. Lütfen bir süre sonra tekrar deneyin.",
      },
      { status: 429 }
    );
  }
  return null;
}

export function anonymousUploadName(mimeType: string): string {
  const ext =
    mimeType === "image/png"
      ? "png"
      : mimeType === "image/webp"
        ? "webp"
        : "jpg";
  const hex = crypto.randomUUID().replace(/-/g, "").slice(0, 16);
  return `upload-${hex}.${ext}`;
}