"use client";

import { useCallback, useMemo, useState } from "react";
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

export default function HomePage() {
  const [username, setUsername] = useState("");
  const [detailed, setDetailed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);

  const grouped = useMemo(
    () => (data ? groupByCategory(data.platforms) : []),
    [data]
  );

  const runSearch = useCallback(async () => {
    const q = username.trim();
    if (!q) {
      setError("Bir kullanıcı adı girin.");
      return;
    }
    setLoading(true);
    setError("");
    setProgress("Platformlar taranıyor…");
    setData(null);

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: q,
          mode: detailed ? "full" : "quick",
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(typeof json.error === "string" ? json.error : "Arama başarısız.");
        setProgress("");
        return;
      }
      setData(json as SearchResponse);
      const d = json as SearchResponse;
      setProgress(
        `${d.meta.checkedCount} site kontrol edildi · ${d.meta.foundCount} olası eşleşme · ${(d.meta.elapsedMs / 1000).toFixed(1)} sn`
      );
    } catch {
      setError("Sunucuya bağlanılamadı.");
      setProgress("");
    } finally {
      setLoading(false);
    }
  }, [username, detailed]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !loading) void runSearch();
  };

  const copyFoundLinks = useCallback(() => {
    if (!data) return;
    const links = data.platforms
      .filter((p) => p.status === "found")
      .map((p) => p.url)
      .join("\n");
    if (!links) return;
    void navigator.clipboard.writeText(links);
    setProgress("Bulunan bağlantılar panoya kopyalandı.");
  }, [data]);

  return (
    <main>
      <header>
        <h1>Kullanıcı adı arama</h1>
        <p className="lead">
          Girilen takma adı birçok platformda herkese açık profil adresi üzerinden
          kontrol eder ve web arama bağlantıları sunar.
        </p>
        <div className="disclaimer" role="note">
          <strong>Yalnızca herkese açık veriler:</strong> Bu araç oturum açmadan
          erişilebilen profil URL’lerini HTTP ile sorgular. Sonuçlar hatalı pozitif
          veya negatif olabilir; başkalarını rahatsız etmek veya izinsiz takip için
          kullanmayın.
        </div>
      </header>

      <div className="search-bar">
        <input
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="örn. kullanici_adi"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={loading}
          aria-label="Kullanıcı adı"
        />
        <button
          type="button"
          className="btn-primary"
          onClick={() => void runSearch()}
          disabled={loading}
        >
          {loading ? "Taranıyor…" : "Ara"}
        </button>
        <button
          type="button"
          className={`toggle-detail${detailed ? " on" : ""}`}
          onClick={() => setDetailed((v) => !v)}
          disabled={loading}
          aria-pressed={detailed}
        >
          Detaylı mod {detailed ? "(tüm siteler)" : "(hızlı)"}
        </button>
      </div>

      <p className={`progress${error ? " error" : ""}`}>
        {error || progress || "\u00a0"}
      </p>

      {data ? (
        <>
          <div className="meta-row">
            <span className="platform-meta">
              Aranan: <strong>{data.username}</strong> · mod:{" "}
              {data.mode === "full" ? "detaylı" : "hızlı"}
            </span>
            <button
              type="button"
              className="btn-ghost"
              onClick={copyFoundLinks}
              disabled={!data.platforms.some((p) => p.status === "found")}
            >
              Bulunan bağlantıları kopyala
            </button>
          </div>

          {grouped.map(([category, items]) => (
            <section className="category-block" key={category}>
              <h2>{CATEGORY_LABELS[category]}</h2>
              <div className="platform-grid">
                {items.map((p) => (
                  <PlatformRow key={p.platformId} item={p} />
                ))}
              </div>
            </section>
          ))}

          <section className="web-section" aria-labelledby="web-heading">
            <h2 id="web-heading">Web araması</h2>
            <div className="engine-links">
              {data.webSearch.links.map((l) => (
                <a
                  key={l.engine}
                  href={l.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {l.label}&apos;da aç
                </a>
              ))}
            </div>
            <h3 style={{ fontSize: "0.95rem", color: "#c5d0e4" }}>
              Önerilen sorgular
            </h3>
            <ul className="query-list">
              {data.webSearch.suggestedQueries.map((q) => (
                <li key={q.url}>
                  <a href={q.url} target="_blank" rel="noopener noreferrer">
                    {q.label}
                  </a>
                </li>
              ))}
            </ul>

            {data.webSearch.duckDuckGoResults?.length ? (
              <div className="ddg-results">
                <h3>DuckDuckGo (sunucu özeti)</h3>
                {data.webSearch.duckDuckGoNote ? (
                  <p className="ddg-note">{data.webSearch.duckDuckGoNote}</p>
                ) : null}
                {data.webSearch.duckDuckGoResults.map((r) => (
                  <article className="ddg-item" key={r.url}>
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
            ) : data.webSearch.duckDuckGoNote ? (
              <p className="ddg-note">{data.webSearch.duckDuckGoNote}</p>
            ) : null}
          </section>
        </>
      ) : null}
    </main>
  );
}

function PlatformRow({ item }: { item: PlatformResult }) {
  return (
    <div className="platform-row">
      <span className={`badge ${BADGE_CLASS[item.status]}`}>
        {BADGE_LABEL[item.status]}
      </span>
      <div>
        <div className="platform-name">{item.name}</div>
        <div className="platform-meta">
          {item.httpStatus != null ? `HTTP ${item.httpStatus}` : "—"}
          {" · "}
          {item.responseTimeMs} ms
          {item.error ? ` · ${item.error}` : ""}
        </div>
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
