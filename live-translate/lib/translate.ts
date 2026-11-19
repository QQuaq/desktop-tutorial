const MAX_CHUNK = 450;
const cache = new Map<string, string>();

function chunks(text: string): string[] {
  const trimmed = text.trim();
  if (piecesEmpty(trimmed)) return [];
  if (trimmed.length <= MAX_CHUNK) return [trimmed];
  const parts: string[] = [];
  let rest = trimmed;
  while (rest.length > MAX_CHUNK) {
    const slice = rest.slice(0, MAX_CHUNK);
    const breakAt = Math.max(slice.lastIndexOf(" "), slice.lastIndexOf(". "));
    const cut = breakAt > 80 ? breakAt : MAX_CHUNK;
    parts.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trim();
  }
  if (rest) parts.push(rest);
  return parts;
}

function piecesEmpty(trimmed: string): boolean {
  return !trimmed;
}

function isBadTranslation(text: string): boolean {
  return /MYMEMORY WARNING/i.test(text) || /^NEXT AVAILABLE IN/i.test(text);
}

async function viaLocalApi(text: string): Promise<string | null> {
  try {
    const res = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = (await res.json().catch(() => ({}))) as {
      translated?: string;
      error?: string;
    };
    if (!res.ok || !data.translated?.trim()) return null;
    return data.translated.trim();
  } catch {
    return null;
  }
}

async function viaLingva(text: string): Promise<string | null> {
  try {
    const res = await fetch(
      `https://lingva.ml/api/v1/en/tr/${encodeURIComponent(text)}`,
    );
    if (!res.ok) return null;
    const data = (await res.json().catch(() => ({}))) as {
      translation?: string;
    };
    const t = data.translation?.trim();
    return t && !isBadTranslation(t) ? t : null;
  } catch {
    return null;
  }
}

async function viaMyMemory(text: string): Promise<string | null> {
  const url = new URL("https://api.mymemory.translated.net/get");
  url.searchParams.set("q", text);
  url.searchParams.set("langpair", "en|tr");

  try {
    const res = await fetch(url.toString());
    const data = (await res.json().catch(() => ({}))) as {
      responseData?: { translatedText?: string };
      responseStatus?: number;
      responseDetails?: string;
    };

    if (!res.ok || data.responseStatus === 403) return null;

    const translated = data.responseData?.translatedText?.trim();
    if (!translated || isBadTranslation(translated)) return null;
    return translated;
  } catch {
    return null;
  }
}

async function translateChunk(text: string): Promise<string> {
  const cached = cache.get(text);
  if (cached) return cached;

  const providers = [
    () => viaLocalApi(text),
    () => viaLingva(text),
    () => viaMyMemory(text),
  ];

  for (const run of providers) {
    const result = await run();
    if (result) {
      cache.set(text, result);
      return result;
    }
  }

  throw new Error(
    "Çeviri kotası veya servis hatası. Biraz bekleyip tekrar deneyin.",
  );
}

export async function translateEnToTr(text: string): Promise<string> {
  const pieces = chunks(text);
  if (!pieces.length) {
    throw new Error("Çevrilecek metin boş.");
  }
  const results: string[] = [];
  for (const piece of pieces) {
    results.push(await translateChunk(piece));
  }
  return results.join(" ");
}