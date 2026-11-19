const MAX_CHARS = 4500;

function jsonError(message: string, status: number) {
  return Response.json({ error: message }, { status });
}

export async function POST(request: Request) {
  let body: { text?: string };
  try {
    body = await request.json();
  } catch {
    return jsonError("Geçersiz JSON.", 400);
  }

  const raw = typeof body.text === "string" ? body.text.trim() : "";
  if (!raw) {
    return jsonError("Çevrilecek metin boş.", 400);
  }
  if (raw.length > MAX_CHARS) {
    return jsonError("Metin çok uzun.", 400);
  }

  const url = new URL("https://translate.googleapis.com/translate_a/single");
  url.searchParams.set("client", "gtx");
  url.searchParams.set("sl", "en");
  url.searchParams.set("tl", "tr");
  url.searchParams.set("dt", "t");
  url.searchParams.set("q", raw);

  let upstream: Response;
  try {
    upstream = await fetch(url.toString(), {
      headers: { "User-Agent": "Mozilla/5.0 (compatible; LiveEnTr/1.0)" },
    });
  } catch {
    return jsonError("Çeviri servisine ulaşılamadı.", 502);
  }

  if (!upstream.ok) {
    return jsonError("Çeviri servisi hata döndü.", 502);
  }

  let data: unknown;
  try {
    data = await upstream.json();
  } catch {
    return jsonError("Çeviri yanıtı okunamadı.", 502);
  }

  const segments = Array.isArray(data) ? data[0] : null;
  if (!Array.isArray(segments)) {
    return jsonError("Beklenmeyen çeviri biçimi.", 502);
  }

  const translated = segments
    .map((part) => (Array.isArray(part) ? String(part[0] ?? "") : ""))
    .join("")
    .trim();

  if (!translated) {
    return jsonError("Çeviri boş döndü.", 502);
  }

  return Response.json({ translated, source: raw });
}