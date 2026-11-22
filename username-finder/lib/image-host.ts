const UA =
  "Mozilla/5.0 (compatible; UsernameFinder/2.0; +https://github.com/QQuaq/desktop-tutorial)";

/** Geçici herkese açık URL (yaklaşık 1 saat). Görsel sunucuda saklanmaz. */
export async function hostImageTemporarily(
  buffer: Buffer,
  filename: string,
  mimeType: string
): Promise<{ url: string } | { error: string }> {
  const form = new FormData();
  form.append(
    "file",
    new Blob([new Uint8Array(buffer)], { type: mimeType }),
    filename
  );

  try {
    const res = await fetch("https://tmpfiles.org/api/v1/upload", {
      method: "POST",
      headers: { "User-Agent": UA },
      body: form,
      signal: AbortSignal.timeout(25_000),
    });
    if (!res.ok) return { error: "Geçici görsel yüklemesi başarısız." };
    const json = (await res.json()) as {
      status?: string;
      data?: { url?: string };
    };
    const pageUrl = json.data?.url;
    if (!pageUrl) return { error: "Geçici URL alınamadı." };
    const idMatch = pageUrl.match(/tmpfiles\.org\/([A-Za-z0-9]+)\//);
    if (!idMatch) return { error: "Geçici URL ayrıştırılamadı." };
    const direct = `https://tmpfiles.org/dl/${idMatch[1]}/${filename}`;
    return { url: direct };
  } catch {
    return { error: "Geçici yükleme zaman aşımı veya ağ hatası." };
  }
}