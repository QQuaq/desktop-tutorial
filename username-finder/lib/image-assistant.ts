import type { AssistantReport, FaceAnalysis, ImageHit, ImageMeta } from "./types";

function domainLabel(hit: ImageHit): string {
  return hit.siteName || hit.domain || "Bilinmeyen site";
}

const VERDICT_TR: Record<string, string> = {
  aynı_kişi_olası: "aynı kişi olma olasılığı yüksek",
  benzer_yüz: "benzer yüz",
  farklı: "farklı yüz",
};

export function buildImageAssistantReport(
  hits: ImageHit[],
  meta: ImageMeta,
  engineNotes: string[],
  face: FaceAnalysis
): AssistantReport {
  const byDomain = new Map<string, ImageHit[]>();
  for (const h of hits) {
    const key = h.domain || domainLabel(h);
    const list = byDomain.get(key) ?? [];
    list.push(h);
    byDomain.set(key, list);
  }

  const siteFindings: string[] = [];
  for (const [domain, list] of byDomain) {
    const sample = list[0];
    const title = sample.title ? ` — «${sample.title.slice(0, 80)}»` : "";
    const kinds = [...new Set(list.map((x) => x.matchKind))].join(", ");
    const faceHits = list.filter((x) => x.faceMatch);
    const faceNote =
      faceHits.length > 0
        ? ` Yüz tanıma: ${faceHits
            .map(
              (x) =>
                `${VERDICT_TR[x.faceMatch!.verdict] ?? x.faceMatch!.verdict} (%${x.faceMatch!.similarity})`
            )
            .join("; ")}.`
        : "";
    siteFindings.push(
      `${domain} sitesinde bu görsel veya çok benzeyen bir görsel bulundu (${list.length} kayıt; ${kinds})${title}.${faceNote}`
    );
  }

  const uniqueDomains = byDomain.size;
  const strongFace = hits.filter((h) => h.faceMatch?.verdict === "aynı_kişi_olası");
  let confidence: AssistantReport["confidence"] = "düşük";
  if (
    uniqueDomains >= 3 ||
    hits.some((h) => h.matchKind === "aynı_görsel") ||
    strongFace.length >= 2
  ) {
    confidence = "yüksek";
  } else if (
    uniqueDomains >= 1 &&
    (hits.length >= 2 || strongFace.length >= 1)
  ) {
    confidence = "orta";
  }

  const headline =
    hits.length === 0
      ? "Görsel eşleşmesi bulunamadı"
      : `${uniqueDomains} farklı kaynakta ${hits.length} görsel sinyali`;

  const summary =
    hits.length === 0
      ? "Yandex ve Bing taramasında güvenilir eşleşme çıkmadı. Farklı bir fotoğraf, daha yüksek çözünürlük veya yüzün net göründüğü bir kare deneyin."
      : `Yüklediğiniz görsel (${meta.width ?? "?"}×${meta.height ?? "?"} px) için ${hits.length} sonuç toplandı.${
          face.detected
            ? ` Yüz tanıma: ${face.faceCount} yüz algılandı; bulunan küçük resimlerdeki yüzler karşılaştırıldı.`
            : " Yüz algılanamadı — yalnızca görsel benzerliği kullanıldı."
        } Kesin kimlik için sonuçları elle doğrulayın.`;

  const bullets = [
    `Güven seviyesi: ${confidence} (${uniqueDomains} site / ${hits.length} kayıt).`,
    face.detected
      ? `Yüz tanıma aktif (${face.faceCount} yüz). ${
          strongFace.length
            ? `${strongFace.length} kayıtta aynı kişi olasılığı yüksek.`
            : "Henüz güçlü yüz eşleşmesi yok."
        }`
      : face.note ?? "Yüz tanıma kullanılamadı.",
    meta.likelyPortrait
      ? "Görsel portre oranında — profil fotoğrafı taramasına uygun."
      : "Görsel geniş format — tersine arama yine de denendi.",
    ...engineNotes.slice(0, 3),
  ];

  const recommendations: string[] = [];
  if (hits.length === 0) {
    recommendations.push(
      "Telefonda Yandex Görsel veya Google Lens ile aynı fotoğrafı yükleyin (uygulama bağlantıları sonuçların altında)."
    );
  } else {
    recommendations.push(
      "Yeşil «güçlü» satırları önce açın; altyazıdaki site gerçekten aynı kişiyi gösteriyor mu kontrol edin."
    );
    if (confidence !== "yüksek") {
      recommendations.push(
        "Birden fazla motorda aynı domain çıkmadı — yanlış pozitif olabilir."
      );
    }
  }

  return {
    headline,
    summary,
    bullets,
    siteFindings,
    recommendations,
    confidence,
  };
}