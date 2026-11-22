export async function readApiResponse(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text.trim()) {
    return {};
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    if (res.status === 401 || res.status === 403) {
      throw new Error(
        "Oturum doğrulanamadı. Uygulamayı Cursor’dan açtığınızdan emin olun."
      );
    }
    if (res.status === 504 || res.status === 502) {
      throw new Error(
        "Sunucu zaman aşımı. Daha az takma ad veya hızlı mod deneyin."
      );
    }
    throw new Error(
      `Sunucu beklenmeyen yanıt verdi (HTTP ${res.status}).`
    );
  }
}

export function errorMessageFromBody(json: unknown, fallback: string): string {
  if (
    json &&
    typeof json === "object" &&
    "error" in json &&
    typeof (json as { error?: unknown }).error === "string"
  ) {
    return (json as { error: string }).error;
  }
  return fallback;
}