const MAX_CHUNK = 450;

function chunks(text: string): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
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

async function translateChunk(text: string): Promise<string> {
  const url = new URL("https://api.mymemory.translated.net/get");
  url.searchParams.set("q", text);
  url.searchParams.set("langpair", "en|tr");

  const res = await fetch(url.toString());
  const data = (await res.json().catch(() => ({}))) as {
    responseData?: { translatedText?: string };
    responseStatus?: number;
    responseDetails?: string;
  };

  if (!res.ok || data.responseStatus === 403) {
    throw new Error(data.responseDetails || "Çeviri servisi yanıt vermedi.");
  }

  const translated = data.responseData?.translatedText?.trim();
  if (!translated) {
    throw new Error("Çeviri boş döndü.");
  }
  return translated;
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