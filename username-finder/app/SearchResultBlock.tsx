"use client";

import { useMemo } from "react";
import { CATEGORY_LABELS } from "@/lib/platforms";
import type {
  PlatformCategory,
  PlatformResult,
  SearchResponse,
} from "@/lib/types";

type BadgeKind = PlatformResult["status"];

const BADGE_LABEL: Record<BadgeKind, string> = {
  found: "Bulundu",
  not_found: "Yok",
  unknown: "Belirsiz",
  error: "Hata",
};

const BADGE_CLASS: Record<BadgeKind, string> = {
  found: "badge-found",
  not_found: "badge-not",
  unknown: "badge-unknown",
  error: "badge-error",
};

function groupByCategory(
  items: PlatformResult[]
): [PlatformCategory, PlatformResult[]][] {
  const map = new Map<PlatformCategory, PlatformResult[]>();
  for (const item of items) {
    const list = map.get(item.category) ?? [];
    list.push(item);
    map.set(item.category, list);
  }
  const order: PlatformCategory[] = [
    "sosyal",
    "mesajlaşma",
    "medya",
    "profesyonel",
    "kod",
    "forum",
    "blog",
    "oyun",
  ];
  return order
    .filter((c) => map.has(c))
    .map((c) => [c, map.get(c)!] as [PlatformCategory, PlatformResult[]]);
}

export function SearchResultBlock({
  data,
  hasPersonHints,
  onCopy,
}: {
  data: SearchResponse;
  hasPersonHints: boolean;
  onCopy: () => void;
}) {
  const grouped = useMemo(
    () => groupByCategory(data.platforms),
    [data.platforms]
  );

  return (
    <section className="nickname-block">
      <header className="nickname-header">
        <h2 className="nickname-title">
          {data.generatedFromName ? "Tahmini nick (ad/soyad): " : "Takma ad: "}
          {data.username}
        </h2>
        {data.person?.firstName || data.person?.lastName ? (
          <span className="platform-meta">
            Kişi:{" "}
            <strong>
              {[data.person.firstName, data.person.lastName]
                .filter(Boolean)
                .join(" ")}
            </strong>
          </span>
        ) : null}
        <span className="platform-meta">
          {data.meta.foundCount} profil ·{" "}
          {data.meta.strongIdentityMatchCount > 0
            ? `${data.meta.strongIdentityMatchCount} güçlü kimlik eşleşmesi`
            : `${data.meta.identityMatchCount} kimlik sinyali`}
        </span>
        <button
          type="button"
          className="btn-ghost"
          onClick={onCopy}
          disabled={!data.platforms.some((p) => p.status === "found")}
        >
          Bu ad için bağlantıları kopyala
        </button>
      </header>

      {data.identityHighlights.length > 0 ? (
        <section className="identity-section" aria-labelledby={`id-${data.username}`}>
          <h3 id={`id-${data.username}`}>Kimlik analizi — {data.username}</h3>
          <ul className="identity-list">
            {data.identityHighlights.map((h) => (
              <li
                key={`${data.username}-${h.url}`}
                className={`identity-card${h.strongMatch ? " strong" : ""}`}
              >
                <div className="identity-card-head">
                  <strong>{h.platformName}</strong>
                  {h.strongMatch ? (
                    <span className="chip-strong">Güçlü örtüşme</span>
                  ) : null}
                </div>
                <p className="identity-summary">{h.summary}</p>
                <a
                  href={h.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="identity-link"
                >
                  Aç
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : hasPersonHints && data.meta.foundCount > 0 ? (
        <p className="identity-empty">
          Profil var ama doğum/konum metinde görünmedi ({data.username}).
        </p>
      ) : null}

      {grouped.map(([category, items]) => (
        <section className="category-block" key={`${data.username}-${category}`}>
          <h3>{CATEGORY_LABELS[category]}</h3>
          <div className="platform-grid">
            {items.map((p) => (
              <PlatformRow key={p.platformId} item={p} />
            ))}
          </div>
        </section>
      ))}

      <section className="web-section">
        <h3>Arama motoru — {data.username}</h3>
        {data.webSearch.engineScans.map((scan) => (
          <div className="engine-block" key={`${data.username}-${scan.engine}`}>
            <h4>
              {scan.label} (
              {scan.results.length > 0 ? scan.results.length : scan.status})
            </h4>
            {scan.note ? <p className="ddg-note">{scan.note}</p> : null}
            {scan.results.map((r) => (
              <article className="ddg-item" key={`${scan.engine}-${r.url}`}>
                <a
                  className="title"
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {r.title}
                </a>
                <div className="url">{r.url}</div>
              </article>
            ))}
          </div>
        ))}
      </section>
    </section>
  );
}

function PlatformRow({ item }: { item: PlatformResult }) {
  return (
    <div className="platform-row">
      <span className={`badge ${BADGE_CLASS[item.status]}`}>
        {BADGE_LABEL[item.status]}
      </span>
      <div className="platform-body">
        <div className="platform-name">{item.name}</div>
        {item.identity && item.identity.matchedCount > 0 ? (
          <p
            className={`platform-identity${item.identity.strongMatch ? " strong" : ""}`}
          >
            {item.identity.summary}
          </p>
        ) : null}
      </div>
      <a
        className="platform-link"
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
      >
        Profili aç
      </a>
    </div>
  );
}