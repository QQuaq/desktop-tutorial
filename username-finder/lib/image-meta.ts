import sizeOf from "image-size";
import type { ImageMeta } from "./types";

export function readImageMeta(buffer: Buffer, mimeType: string): ImageMeta {
  let width: number | undefined;
  let height: number | undefined;
  let type: string | undefined;
  try {
    const dim = sizeOf(buffer);
    width = dim.width;
    height = dim.height;
    type = dim.type;
  } catch {
    type = mimeType.split("/")[1];
  }
  const likelyPortrait = Boolean(
    width && height && height >= width * 0.9 && height > 200
  );
  const likelyFacePhoto = Boolean(
    width &&
      height &&
      width >= 80 &&
      height >= 80 &&
      Math.max(width, height) / Math.min(width, height) < 2.2
  );
  return {
    width,
    height,
    type,
    byteLength: buffer.length,
    likelyPortrait,
    likelyFacePhoto,
  };
}