"use client";

import { useCallback, useMemo, useState } from "react";
import { CATEGORY_LABELS } from "@/lib/platforms";
import type {
  PersonHintsInput,
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

const EMPTY_PERSON: PersonHintsInput = {
  firstName: "",
  lastName: "",
  birthDate: "",
  location: "",
};

export default function HomePage() {
  const [username, setUsername] = useState("");
  const [person, setPerson] = useState<PersonHintsInput>({ ...EMPTY_PERSON });
  const [detailed, setDetailed] = useState(true);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const grouped = useMemo(
    () => (data ? groupByCategory(data.platforms) : []),
    [data]
  );

  const hasPersonHints = useMemo(
    () =>
      Boolean(
        person.firstName?.trim() ||
          person.lastName?.trim() ||
          person.birthDate?.trim() ||
          person.location?.trim()
      ),
    [person]
  );

  const runSearch = useCallback(async () => {
    const q = username.trim();
    if (!q) {
      setError("Bir kullanıcı adı girin.");
      return;
    }
    setLoading(true);
    setError("");
    setProgress(
      "Platformlar + DuckDuckGo, Bing ve Yandex motorları taranıyor…"
    );
    setData(null);

    const personPayload: PersonHintsInput | undefined = hasPersonHints
      ? {
          firstName: person.firstName?.trim() || undefined,
          lastName: person.lastName?.trim() || undefined,
          birthDate: person.birthDate?.trim() || undefined,
          location: person.location?.trim() || undefined,
        }
      : undefined;

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: q,
          mode: hasPersonHints || detailed ? "full" : "quick",
          person: personPayload,
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
      const idPart =
        d.meta.strongIdentityMatchCount > 0
          ? ` · ${d.meta.strongIdentityMatchCount} güçlü kimlik örtüşmesi`
          : d.meta.identityMatchCount > 0
            ? ` · ${d.meta.identityMatchCount} kısmi kimlik örtüşmesi`
            : hasPersonHints
              ? " · kimlik alanları sayfalarda eşleşmedi"
              : "";
      const engPart =
        d.meta.engineHitCount > 0
          ? ` · ${d.meta.engineHitCount} arama motoru sonucu`
          : "";
      setProgress(
        `${d.meta.checkedCount} site · ${d.meta.foundCount} profil${engPart}${idPart} · ${(d.meta.elapsedMs / 1000).toFixed(1)} sn`
      );
    } catch {
      setError("Sunucuya bağlanılamadı.");
      setProgress("");
    } finally {
      setLoading(false);
    }
  }, [username, detailed, hasPersonHints, person]);

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

  const setPersonField = (key: keyof PersonHintsInput, value: string) => {
    setPerson((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <main>
      <header>
        <h1>Kullanıcı adı arama</h1>
        <p className="lead">
          Platform taramasına ek olarak DuckDuckGo, Bing ve Yandex (mümkünse
          sunucu üzerinden) metin araması yapar. İsim, doğum ve şehir girilince
          sonuç metinlerinde de eşleşme arar.
        </p>
        <div className="disclaimer" role="note">
          <strong>Yalnızca herkese açık veriler:</strong> Sonuçlar hatalı olabilir;
          birçok sitede doğum yeri veya tarih hiç görünmez. Kesin kimlik için
          profilleri elle doğrulayın.
        </div>
      </header>

      <section className="person-form" aria-labelledby="person-heading">
        <h2 id="person-heading">Kimlik bilgileri (isteğe bağlı)</h2>
        <p className="person-hint">
          Hepsini doldurursanız, doğum tarihi ve şehir aynı sayfada geçiyorsa
          &quot;güçlü örtüşme&quot; olarak işaretlenir.
        </p>
        <div className="person-grid">
          <label>
            Ad
            <input
              type="text"
              autoComplete="off"
              value={person.firstName ?? ""}
              onChange={(e) => setPersonField("firstName", e.target.value)}
              disabled={loading}
            />
          </label>
          <label>
            Soyad
            <input
              type="text"
              autoComplete="off"
              value={person.lastName ?? ""}
              onChange={(e) => setPersonField("lastName", e.target.value)}
              disabled={loading}
            />
          </label>
          <label>
            Doğum tarihi
            <input
              type="text"
              placeholder="gg.aa.yyyy veya yıl"
              autoComplete="off"
              value={person.birthDate ?? ""}
              onChange={(e) => setPersonField("birthDate", e.target.value)}
              disabled={loading}
            />
          </label>
          <label>
            Yaşadığı yer
            <input
              type="text"
              placeholder="örn. İstanbul"
              autoComplete="off"
              value={person.location ?? ""}
              onChange={(e) => setPersonField("location", e.target.value)}
              disabled={loading}
            />
          </label>
        </div>
      </section>

      <section className="image-form" aria-labelledby="image-heading">
        <h2 id="image-heading">Resimle arama</h2>
        <p className="person-hint">
          Profil fotoğrafı seçerseniz önizleme gösterilir. Tam otomatik tersine
          görsel tarama sunucuda saklanmadan mümkün değil; arama sonrası Yandex
          Görsel, Google Lens ve Bing bağlantıları listelenir.
        </p>
        <input
          type="file"
          accept="image/*"
          disabled={loading}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (!file) {
              setImagePreview(null);
              return;
            }
            if (file.size > 1_500_000) {
              setError("Resim en fazla ~1,5 MB olabilir.");
              setImagePreview(null);
              return;
            }
            const reader = new FileReader();
            reader.onload = () =>
              setImagePreview(
                typeof reader.result === "string" ? reader.result : null
              );
            reader.readAsDataURL(file);
          }}
        />
        {imagePreview ? (
          <img
            src={imagePreview}
            alt="Seçilen profil fotoğrafı önizlemesi"
            className="image-preview"
          />
        ) : null}
      </section>

      <div className="search-bar">
        <input
          type="search"
          autoComplete="off"
          spellCheck={false}
          placeholder="Kullanıcı adı (örn. kullanici_adi)"
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
          {loading ? "Taranıyor…" : "Detaylı tara"}
        </button>
        <button
          type="button"
          className={`toggle-detail${detailed ? " on" : ""}`}
          onClick={() => setDetailed((v) => !v)}
          disabled={loading || hasPersonHints}
          aria-pressed={detailed}
          title={
            hasPersonHints
              ? "Kimlik bilgisi varken her zaman tüm siteler taranır"
              : undefined
          }
        >
          {hasPersonHints
            ? "Tüm siteler (kimlik modu)"
            : detailed
              ? "Tüm siteler"
              : "Hızlı (~15 site)"}
        </button>
      </div>

      <p className={`progress${error ? " error" : ""}`}>
        {error || progress || "\u00a0"}
      </p>

      {data ? (
        <>
          <div className="meta-row">
            <span className="platform-meta">
              Aranan: <strong>{data.username}</strong>
              {data.person?.firstName || data.person?.lastName ? (
                <>
                  {" "}
                  ·{" "}
                  <strong>
                    {[data.person.firstName, data.person.lastName]
                      .filter(Boolean)
                      .join(" ")}
                  </strong>
                </>
              ) : null}
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

          {data.identityHighlights.length > 0 ? (
            <section className="identity-section" aria-labelledby="identity-heading">
              <h2 id="identity-heading">Kimlik analizi</h2>
              <p className="identity-lead">
                Aşağıdaki sitelerde girdiğiniz bilgilerle örtüşen metin bulundu
                (sayfa HTML’inde arama; her site her alanı göstermez).
              </p>
              <ul className="identity-list">
                {data.identityHighlights.map((h) => (
                  <li
                    key={h.url}
                    className={`identity-card${h.strongMatch ? " strong" : ""}`}
                  >
                    <div className="identity-card-head">
                      <strong>{h.platformName}</strong>
                      {h.strongMatch ? (
                        <span className="chip-strong">Güçlü örtüşme</span>
                      ) : null}
                    </div>
                    <p className="identity-summary">{h.summary}</p>
                    <div className="match-chips">
                      {h.matchedLabels.map((label) => (
                        <span className="chip-match" key={label}>
                          {label}
                        </span>
                      ))}
                    </div>
                    <a
                      href={h.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="identity-link"
                    >
                      Profili aç
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          ) : hasPersonHints && data.meta.foundCount > 0 ? (
            <p className="identity-empty">
              Profil bulundu ancak girdiğiniz ad, doğum veya konum bilgisi
              sayfa metninde eşleşmedi (site biyografide göstermiyor olabilir).
            </p>
          ) : null}

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

          <section className="web-section" aria-labelledby="engines-heading">
            <h2 id="engines-heading">Arama motoru taraması</h2>
            <p className="web-note">
              Sonuçlar sunucuda toplanır; Yandex bazen captcha nedeniyle boş
              kalabilir — o zaman alttaki Yandex bağlantılarını telefonda açın.
            </p>
            {data.webSearch.engineScans.map((scan) => (
              <div className="engine-block" key={scan.engine}>
                <h3>
                  {scan.label}{" "}
                  <span className={`engine-status status-${scan.status}`}>
                    {scan.status === "ok"
                      ? `${scan.results.length} sonuç`
                      : scan.status === "blocked"
                        ? "captcha"
                        : "sonuç yok"}
                  </span>
                </h3>
                {scan.note ? <p className="ddg-note">{scan.note}</p> : null}
                {scan.results.map((r) => (
                  <article
                    className={`ddg-item${r.identityMatch?.strongMatch ? " id-strong" : ""}`}
                    key={`${scan.engine}-${r.url}`}
                  >
                    <a
                      className="title"
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {r.title}
                    </a>
                    {r.snippet ? (
                      <p className="hit-snippet">{r.snippet}</p>
                    ) : null}
                    {r.identityMatch &&
                    r.identityMatch.matchedLabels.length > 0 ? (
                      <p className="platform-identity strong">
                        {r.identityMatch.summary}
                      </p>
                    ) : null}
                    <div className="url">{r.url}</div>
                  </article>
                ))}
              </div>
            ))}
          </section>

          <section className="web-section" aria-labelledby="image-links-heading">
            <h2 id="image-links-heading">Görsel arama bağlantıları</h2>
            <p className="web-note">
              Resim yükleme motorları tarayıcıda çalışır; fotoğrafı siz
              yüklersiniz.
            </p>
            <ul className="image-offer-list">
              {data.webSearch.imageSearch.map((offer) => (
                <li key={offer.engine}>
                  <a href={offer.url} target="_blank" rel="noopener noreferrer">
                    {offer.label}
                  </a>
                  <span className="offer-note">{offer.note}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="web-section" aria-labelledby="web-heading">
            <h2 id="web-heading">Tarayıcıda derin arama</h2>
            <div className="engine-links">
              {data.webSearch.links.map((l) => (
                <a
                  key={l.engine}
                  href={l.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {l.label}&apos;de aç
                </a>
              ))}
            </div>
            <ul className="query-list">
              {data.webSearch.suggestedQueries.map((q) => (
                <li key={q.url}>
                  <a href={q.url} target="_blank" rel="noopener noreferrer">
                    {q.label}
                  </a>
                </li>
              ))}
            </ul>
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
      <div className="platform-body">
        <div className="platform-name">{item.name}</div>
        <div className="platform-meta">
          {item.httpStatus != null ? `HTTP ${item.httpStatus}` : "—"}
          {" · "}
          {item.responseTimeMs} ms
          {item.error ? ` · ${item.error}` : ""}
        </div>
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