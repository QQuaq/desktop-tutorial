import { buildImageAssistantReport } from "@/lib/image-assistant";
import { enrichHitsWithFaceMatch, scanFacesInBuffer } from "@/lib/face-recognition";
import {
  enforceRateLimit,
  requireSignedInViewer,
} from "@/lib/http-guard";
import { readImageMeta } from "@/lib/image-meta";
import { validateImagePayload, MAX_IMAGE_BYTES } from "@/lib/image-search";
import { runReverseImageSearch } from "@/lib/reverse-image";
import type { ImageSearchResponse } from "@/lib/types";

export const maxDuration = 120;

const PRIVACY_NOTICE =
  "Fotoğraf bu sunucuda saklanmaz. Onayınızla Yandex ve Bing aramasına doğrudan gönderilir; yüz karşılaştırması yalnızca bulunan küçük resimleri geçici indirir.";

function jsonError(message: string, status: number) {
  return Response.json({ error: message }, { status });
}

export async function POST(request: Request) {
  const auth = await requireSignedInViewer(request);
  if (!auth.ok) return auth.response;

  const limited = await enforceRateLimit(
    request,
    "image-search",
    12,
    60 * 60_000
  );
  if (limited) return limited;

  const started = Date.now();
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return jsonError("Geçersiz form verisi.", 400);
  }

  const consent = form.get("privacyConsent");
  if (consent !== "yes") {
    return jsonError(
      "Devam etmek için gizlilik onayını işaretleyin (privacyConsent=yes).",
      400
    );
  }

  const file = form.get("image");
  if (!file || !(file instanceof Blob)) {
    return jsonError("Bir resim dosyası gönderin (alan: image).", 400);
  }

  const buffer = Buffer.from(await file.arrayBuffer());
  if (buffer.length > MAX_IMAGE_BYTES) {
    return jsonError("Resim en fazla ~1,5 MB olabilir.", 400);
  }

  const mimeType = file.type || "image/jpeg";
  const err = validateImagePayload(mimeType, buffer.length);
  if (err) return jsonError(err, 400);

  const meta = readImageMeta(buffer, mimeType);
  const [faceScan, reverse] = await Promise.all([
    scanFacesInBuffer(buffer),
    runReverseImageSearch(buffer, mimeType),
  ]);
  const { hits, engineNotes } = reverse;
  const face = faceScan.analysis;

  if (faceScan.descriptor) {
    await enrichHitsWithFaceMatch(faceScan.descriptor, hits);
  }

  const assistant = buildImageAssistantReport(hits, meta, engineNotes, face);

  const payload: ImageSearchResponse = {
    meta,
    hits,
    assistant,
    engineNotes,
    face,
    privacyNotice: PRIVACY_NOTICE,
    elapsedMs: Date.now() - started,
  };

  return Response.json(payload);
}