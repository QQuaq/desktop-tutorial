import type { AssistantReport, ImageHit, ImageMeta } from "./types";

function domainLabel(hit: ImageHit): string {
  return hit.siteName || hit.domain || "Bilinmeyen site";
}

export function buildImageAssistantReport(
  hits: ImageHit[],
  meta: ImageMeta,
  engineNotes: string[]
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
    siteFindings.push(
      `${domain} sitesinde bu görsel veya çok benzeyen bir görsel bulundu (${list.length} kayıt; ${kinds})${title}.`
    );
  }

  const uniqueDomains = byDomain.size;
  let confidence: AssistantReport["confidence"] = "düşük";
  if (uniqueDomains >= 3 || hits.some((h) => h.matchKind === "aynı_görsel")) {
    confidence = "yüksek";
  } else if (uniqueDomains >= 1 && hits.length >= 2) {
    confidence = "orta";
  }

  const headline =
    hits.length === 0
      ? "Görsel eşleşmesi bulunamadı"
      : `${uniqueDomains} farklı kaynakta ${hits.length} görsel sinyali`;

  const summary =
    hits.length === 0
      ? "Yandex, Bing ve (varsa) Google Lens taramasında güvenilir eşleşme çıkmadı. Farklı bir fotoğraf, daha yüksek çözünürlük veya yüzün net göründüğü bir kare deneyin."
      : `Yüklediğiniz görsel (${meta.width ?? "?"}×${meta.height ?? "?"} px) için ${hits.length} sonuç toplandı. Aynı kişiye ait profil fotoğraflarında genelde ${meta.likelyFacePhoto ? "yüz/portre" : "genel"} görsel araması işe yarar; kesin kimlik için sonuçları elle doğrulayın.`;

  const bullets = [
    `Güven seviyesi: ${confidence} (${uniqueDomains} site / ${hits.length} kayıt).`,
    meta.likelyPortrait
      ? "Görsel portre oranında — profil fotoğrafı taramasına uygun."
      : "Görsel geniş format — tersine arama yine de denendi.",
    ...engineNotes.slice(0, 4),
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