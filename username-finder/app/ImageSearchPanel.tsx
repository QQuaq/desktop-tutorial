"use client";

import { useCallback, useState } from "react";
import type { ImageHit, ImageSearchResponse } from "@/lib/types";

const KIND_LABEL: Record<ImageHit["matchKind"], string> = {
  aynı_görsel: "Aynı / çok yakın görsel",
  benzer_görsel: "Benzer görsel",
  ilgili_sayfa: "İlgili sayfa",
  bilinmiyor: "Belirsiz",
};

export function ImageSearchPanel() {
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<ImageSearchResponse | null>(null);

  const onFile = (f: File | null) => {
    setFile(f);
    setData(null);
    setError("");
    if (!f) {
      setPreview(null);
      return;
    }
    if (f.size > 1_500_000) {
      setError("Resim en fazla ~1,5 MB olabilir.");
      setFile(null);
      return;
    }
    const reader = new FileReader();
    reader.onload = () =>
      setPreview(typeof reader.result === "string" ? reader.result : null);
    reader.readAsDataURL(f);
  };

  const runImageSearch = useCallback(async () => {
    if (!file) {
      setError("Önce bir fotoğraf seçin.");
      return;
    }
    setLoading(true);
    setError("");
    setData(null);
    try {
      const body = new FormData();
      body.append("image", file);
      const res = await fetch("/api/image-search", {
        method: "POST",
        body,
      });
      const json: unknown = await res.json();
      if (!res.ok) {
        const msg =
          json &&
          typeof json === "object" &&
          "error" in json &&
          typeof (json as { error?: unknown }).error === "string"
            ? (json as { error: string }).error
            : "Resim araması başarısız.";
        setError(msg);
        return;
      }
      setData(json as ImageSearchResponse);
    } catch {
      setError("Sunucuya bağlanılamadı.");
    } finally {
      setLoading(false);
    }
  }, [file]);

  return (
    <section className="image-search-panel" aria-labelledby="img-search-heading">
      <h2 id="img-search-heading">Resimle detaylı arama</h2>
      <p className="person-hint">
        Fotoğraf yükleyin; Yandex, Bing ve (varsa API anahtarı ile) Google Lens
        üzerinden tersine arama yapılır. <strong>Yardımcı AI</strong> sonuçları
        özetler: hangi sitede benzer görsel bulunduğu satır satır yazılır.
      </p>

      <input
        type="file"
        accept="image/*"
        disabled={loading}
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />

      {preview ? (
        <img src={preview} alt="Seçilen fotoğraf" className="image-preview" />
      ) : null}

      <button
        type="button"
        className="btn-primary image-search-btn"
        disabled={loading || !file}
        onClick={() => void runImageSearch()}
      >
        {loading ? "Görsel taranıyor…" : "Sadece resimle ara"}
      </button>

      {error ? <p className="progress error">{error}</p> : null}

      {data ? (
        <>
          <article className="assistant-card">
            <h3>Yardımcı AI özeti</h3>
            <p className="assistant-headline">{data.assistant.headline}</p>
            <p className="assistant-summary">{data.assistant.summary}</p>
            <ul className="assistant-bullets">
              {data.assistant.bullets.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
            {data.assistant.siteFindings.length > 0 ? (
              <>
                <h4>Site bulguları</h4>
                <ul className="site-findings">
                  {data.assistant.siteFindings.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </>
            ) : null}
            <h4>Öneriler</h4>
            <ul className="assistant-bullets">
              {data.assistant.recommendations.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </article>

          <h3 className="hits-heading">
            Detaylı kayıtlar ({data.hits.length})
          </h3>
          {data.hits.length === 0 ? (
            <p className="identity-empty">
              Otomatik motorlarda kayıt yok. Altta Yandex Görsel / Lens
              bağlantılarını deneyin.
            </p>
          ) : (
            <ul className="image-hit-list">
              {data.hits.map((h) => (
                <li
                  key={`${h.engine}-${h.pageUrl}`}
                  className={
                    h.confidence >= 75
                      ? "image-hit strong"
                      : "image-hit"
                  }
                >
                  <div className="hit-top">
                    <strong>
                      {h.siteName || h.domain}
                    </strong>
                    <span className="chip-match">{KIND_LABEL[h.matchKind]}</span>
                    <span className="chip-confidence">
                      güven %{h.confidence}
                    </span>
                  </div>
                  <p className="hit-line">
                    {h.engine}: bu sitede eşleşme —{" "}
                    <a href={h.pageUrl} target="_blank" rel="noopener noreferrer">
                      sayfayı aç
                    </a>
                  </p>
                  {h.title ? <p className="hit-snippet">{h.title}</p> : null}
                </li>
              ))}
            </ul>
          )}

          <p className="ddg-note">
            Süre: {(data.elapsedMs / 1000).toFixed(1)} sn
            {data.tempImageUrl
              ? " · geçici görsel URL ile tarandı"
              : ""}
          </p>
        </>
      ) : null}
    </section>
  );
}