"use client";

import { useCallback, useMemo, useState } from "react";
import { SearchResultBlock } from "./SearchResultBlock";
import type {
  BatchSearchResponse,
  PersonHintsInput,
  SearchResponse,
} from "@/lib/types";

const EMPTY_PERSON: PersonHintsInput = {
  firstName: "",
  lastName: "",
  birthDate: "",
  location: "",
};

export default function HomePage() {
  const [nicknames, setNicknames] = useState(["", "", ""]);
  const [person, setPerson] = useState<PersonHintsInput>({ ...EMPTY_PERSON });
  const [detailed, setDetailed] = useState(true);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [results, setResults] = useState<SearchResponse[] | null>(null);
  const [batchMeta, setBatchMeta] = useState<BatchSearchResponse["meta"] | null>(
    null
  );
  const [imagePreview, setImagePreview] = useState<string | null>(null);

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

  const setPersonField = (key: keyof PersonHintsInput, value: string) => {
    setPerson((prev) => ({ ...prev, [key]: value }));
  };

  const runSearch = useCallback(async () => {
    const names = nicknames.map((n) => n.trim()).filter(Boolean).slice(0, 3);
    if (names.length === 0) {
      setError("En az bir takma ad girin (en fazla 3).");
      return;
    }
    setLoading(true);
    setError("");
    setProgress(
      names.length > 1
        ? `${names.length} takma ad sırayla taranıyor…`
        : "Taranıyor…"
    );
    setResults(null);
    setBatchMeta(null);

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
          usernames: names,
          mode: hasPersonHints || detailed ? "full" : "quick",
          person: personPayload,
        }),
      });
      const json: unknown = await res.json();
      if (!res.ok) {
        const errMsg =
          json &&
          typeof json === "object" &&
          "error" in json &&
          typeof (json as { error?: unknown }).error === "string"
            ? (json as { error: string }).error
            : "Arama başarısız.";
        setError(errMsg);
        setProgress("");
        return;
      }

      if (
        json &&
        typeof json === "object" &&
        "batch" in json &&
        (json as BatchSearchResponse).batch === true
      ) {
        const batch = json as BatchSearchResponse;
        setResults(batch.items);
        setBatchMeta(batch.meta);
        setProgress(
          `${batch.meta.usernameCount} takma ad · ${batch.meta.totalFound} profil · ${(batch.meta.totalElapsedMs / 1000).toFixed(1)} sn`
        );
      } else {
        const single = json as SearchResponse;
        setResults([single]);
        setProgress(
          `${single.meta.foundCount} profil · ${(single.meta.elapsedMs / 1000).toFixed(1)} sn`
        );
      }
    } catch {
      setError("Sunucuya bağlanılamadı.");
      setProgress("");
    } finally {
      setLoading(false);
    }
  }, [nicknames, detailed, hasPersonHints, person]);

  const setNickname = (index: number, value: string) => {
    setNicknames((prev) => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  };

  return (
    <main>
      <header>
        <h1>Kullanıcı adı arama</h1>
        <p className="lead">
          Aynı anda en fazla <strong>3 takma ad</strong> sırayla taranır. Doğum
          tarihi ve yaşadığı yeri doldurunca bulunan sayfalarda eşleşme aranır.
        </p>
      </header>

      <section className="nickname-form" aria-labelledby="nick-heading">
        <h2 id="nick-heading">Takma adlar (1–3)</h2>
        <div className="nickname-grid">
          {nicknames.map((value, i) => (
            <label key={i}>
              {i + 1}. takma ad
              <input
                type="search"
                autoComplete="off"
                spellCheck={false}
                placeholder={i === 0 ? "zorunlu" : "isteğe bağlı"}
                value={value}
                onChange={(e) => setNickname(i, e.target.value)}
                disabled={loading}
              />
            </label>
          ))}
        </div>
      </section>

      <section className="person-form person-form-highlight" aria-labelledby="person-heading">
        <h2 id="person-heading">Doğum tarihi ve yaşadığı yer</h2>
        <p className="person-hint">
          Ad, soyad, <strong>doğum tarihi</strong> ve <strong>yaşadığı yer</strong>{" "}
          tüm takma adlar için ortaktır; aynı kişiye ait profillerde metin
          eşleşmesi aranır.
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
          <label className="field-emphasis">
            Doğum tarihi
            <input
              type="text"
              placeholder="örn. 15.05.1995"
              autoComplete="off"
              value={person.birthDate ?? ""}
              onChange={(e) => setPersonField("birthDate", e.target.value)}
              disabled={loading}
            />
          </label>
          <label className="field-emphasis">
            Yaşadığı yer
            <input
              type="text"
              placeholder="örn. İstanbul, Türkiye"
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
            alt="Önizleme"
            className="image-preview"
          />
        ) : null}
      </section>

      <div className="search-bar">
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
        >
          {hasPersonHints ? "Tüm siteler" : detailed ? "Tüm siteler" : "Hızlı"}
        </button>
      </div>

      <p className={`progress${error ? " error" : ""}`}>
        {error || progress || "\u00a0"}
      </p>

      {batchMeta && batchMeta.usernameCount > 1 ? (
        <p className="batch-summary">
          Toplam: {batchMeta.totalFound} profil,{" "}
          {batchMeta.totalStrongIdentity} güçlü kimlik eşleşmesi
        </p>
      ) : null}

      {results?.map((data) => (
        <SearchResultBlock
          key={data.username}
          data={data}
          hasPersonHints={hasPersonHints}
          onCopy={() => {
            const links = data.platforms
              .filter((p) => p.status === "found")
              .map((p) => p.url)
              .join("\n");
            if (links) void navigator.clipboard.writeText(links);
          }}
        />
      ))}
    </main>
  );
}