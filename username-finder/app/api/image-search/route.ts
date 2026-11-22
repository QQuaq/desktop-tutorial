import { buildImageAssistantReport } from "@/lib/image-assistant";
import { enrichHitsWithFaceMatch, scanFacesInBuffer } from "@/lib/face-recognition";
import { readImageMeta } from "@/lib/image-meta";
import { validateImagePayload, MAX_IMAGE_BYTES } from "@/lib/image-search";
import { runReverseImageSearch } from "@/lib/reverse-image";
import type { ImageSearchResponse } from "@/lib/types";

export const maxDuration = 120;

function jsonError(message: string, status: number) {
  return Response.json({ error: message }, { status });
}

export async function POST(request: Request) {
  const started = Date.now();
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return jsonError("Geçersiz form verisi.", 400);
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

  const name =
    file instanceof File && file.name ? file.name : `upload.${mimeType.split("/")[1] || "jpg"}`;

  const meta = readImageMeta(buffer, mimeType);
  const [faceScan, reverse] = await Promise.all([
    scanFacesInBuffer(buffer),
    runReverseImageSearch(buffer, name, mimeType),
  ]);
  const { hits, engineNotes, tempImageUrl } = reverse;
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
    tempImageUrl,
    face,
    elapsedMs: Date.now() - started,
  };

  return Response.json(payload);
}