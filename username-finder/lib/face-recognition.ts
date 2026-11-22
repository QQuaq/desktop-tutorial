import * as faceapi from "@vladmandic/face-api";
import sharp from "sharp";
import type { FaceAnalysis, FaceVerdict, ImageHit } from "./types";

const MODEL_ROOT =
  "https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.15/model/";
const MAX_COMPARE_BYTES = 900_000;
const FETCH_TIMEOUT_MS = 9_000;
/** face-api önerisi: aynı kişi için genelde < 0.45–0.55 */
const SAME_PERSON_DISTANCE = 0.5;
const SIMILAR_FACE_DISTANCE = 0.62;

let modelsReady: Promise<boolean> | null = null;

async function ensureModels(): Promise<boolean> {
  if (!modelsReady) {
    modelsReady = (async () => {
      try {
        await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_ROOT);
        await faceapi.nets.faceLandmark68TinyNet.loadFromUri(MODEL_ROOT);
        await faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_ROOT);
        return true;
      } catch {
        return false;
      }
    })();
  }
  return modelsReady;
}

async function bufferToTensor(
  buffer: Buffer
): Promise<ReturnType<typeof faceapi.tf.tensor3d> | null> {
  try {
    const { data, info } = await sharp(buffer, { failOn: "none" })
      .rotate()
      .resize(1024, 1024, { fit: "inside", withoutEnlargement: false })
      .ensureAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });

    const pixels = new Uint8Array(info.width * info.height * 3);
    let j = 0;
    for (let i = 0; i < data.length; i += 4) {
      pixels[j++] = data[i];
      pixels[j++] = data[i + 1];
      pixels[j++] = data[i + 2];
    }
    return faceapi.tf.tensor3d(pixels, [info.height, info.width, 3]);
  } catch {
    return null;
  }
}

type FaceDesc = Float32Array;

async function descriptorsFromBuffer(
  buffer: Buffer
): Promise<{ count: number; primary?: FaceDesc; box?: faceapi.Box }> {
  const ok = await ensureModels();
  if (!ok) return { count: 0 };

  const tensor = await bufferToTensor(buffer);
  if (!tensor) return { count: 0 };

  try {
    const opts = new faceapi.TinyFaceDetectorOptions({
      inputSize: 416,
      scoreThreshold: 0.4,
    });
    const faces = await faceapi
      .detectAllFaces(tensor, opts)
      .withFaceLandmarks(true)
      .withFaceDescriptors();

    if (faces.length === 0) return { count: 0 };

    const primary = faces.reduce((a, b) =>
      a.detection.box.area > b.detection.box.area ? a : b
    );
    return {
      count: faces.length,
      primary: primary.descriptor,
      box: primary.detection.box,
    };
  } finally {
    tensor.dispose();
  }
}

function verdictFromDistance(distance: number): FaceVerdict {
  if (distance <= SAME_PERSON_DISTANCE) return "aynı_kişi_olası";
  if (distance <= SIMILAR_FACE_DISTANCE) return "benzer_yüz";
  return "farklı";
}

export function similarityPercent(distance: number): number {
  const norm = Math.max(0, Math.min(1, 1 - distance / 1.05));
  return Math.round(norm * 100);
}

export interface FaceScanResult {
  analysis: FaceAnalysis;
  descriptor: FaceDesc | null;
}

export async function scanFacesInBuffer(buffer: Buffer): Promise<FaceScanResult> {
  const ok = await ensureModels();
  if (!ok) {
    return {
      analysis: {
        detected: false,
        faceCount: 0,
        modelReady: false,
        note: "Yüz modelleri yüklenemedi; yalnızca görsel arama kullanıldı.",
      },
      descriptor: null,
    };
  }

  const { count, primary, box } = await descriptorsFromBuffer(buffer);
  if (count === 0 || !primary) {
    return {
      analysis: {
        detected: false,
        faceCount: 0,
        modelReady: true,
        note: "Yüz bulunamadı. Yüzün net göründüğü bir fotoğraf deneyin.",
      },
      descriptor: null,
    };
  }

  return {
    descriptor: primary,
    analysis: {
      detected: true,
      faceCount: count,
      modelReady: true,
      primaryBox: box
        ? {
            x: Math.round(box.x),
            y: Math.round(box.y),
            width: Math.round(box.width),
            height: Math.round(box.height),
          }
        : undefined,
      note:
        count > 1
          ? `${count} yüz bulundu; en büyük yüz kimlik karşılaştırmasında kullanıldı.`
          : "Yüz tanındı; bulunan görsellerdeki yüzler bu fotoğrafla karşılaştırıldı.",
    },
  };
}

async function fetchImageBuffer(url: string): Promise<Buffer | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { "User-Agent": "UsernameFinder/1.0" },
      redirect: "follow",
    });
    if (!res.ok) return null;
    const buf = Buffer.from(await res.arrayBuffer());
    if (buf.length > MAX_COMPARE_BYTES) return null;
    return buf;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function compareDescriptorToImageUrl(
  source: FaceDesc,
  imageUrl: string
): Promise<{ distance: number; similarity: number; verdict: FaceVerdict } | null> {
  const buf = await fetchImageBuffer(imageUrl);
  if (!buf) return null;
  const { primary } = await descriptorsFromBuffer(buf);
  if (!primary) return null;
  const distance = faceapi.euclideanDistance(source, primary);
  return {
    distance,
    similarity: similarityPercent(distance),
    verdict: verdictFromDistance(distance),
  };
}

export async function enrichHitsWithFaceMatch(
  sourceDesc: FaceDesc | null,
  hits: ImageHit[]
): Promise<void> {
  if (!sourceDesc) return;

  const withImage = hits.filter((h) => h.imageUrl).slice(0, 8);

  await Promise.all(
    withImage.map(async (hit) => {
      if (!hit.imageUrl) return;
      const cmp = await compareDescriptorToImageUrl(sourceDesc, hit.imageUrl);
      if (!cmp) {
        return;
      }
      hit.faceMatch = {
        similarity: cmp.similarity,
        distance: Math.round(cmp.distance * 1000) / 1000,
        verdict: cmp.verdict,
      };
      if (cmp.verdict === "aynı_kişi_olası") {
        hit.confidence = Math.min(98, hit.confidence + 18);
        if (hit.matchKind === "benzer_görsel" || hit.matchKind === "ilgili_sayfa") {
          hit.matchKind = "aynı_görsel";
        }
      } else if (cmp.verdict === "benzer_yüz") {
        hit.confidence = Math.min(95, hit.confidence + 8);
      }
    })
  );
}