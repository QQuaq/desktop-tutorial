"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type SpeechRecognitionCtor = new () => SpeechRecognition;

function getSpeechRecognition(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as Window &
    typeof globalThis & {
      webkitSpeechRecognition?: SpeechRecognitionCtor;
      SpeechRecognition?: SpeechRecognitionCtor;
    };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

async function translateText(text: string): Promise<string> {
  const res = await fetch("/api/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const data = (await res.json().catch(() => ({}))) as {
    translated?: string;
    error?: string;
  };
  if (!res.ok) {
    throw new Error(data.error || `Çeviri hatası (${res.status})`);
  }
  return data.translated ?? "";
}

export default function HomePage() {
  const [supported, setSupported] = useState<boolean | null>(null);
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState("");
  const [statusKind, setStatusKind] = useState<"" | "ok" | "error">("");
  const [englishFinal, setEnglishFinal] = useState("");
  const [englishInterim, setEnglishInterim] = useState("");
  const [turkishFinal, setTurkishFinal] = useState("");
  const [turkishInterim, setTurkishInterim] = useState("");
  const [translating, setTranslating] = useState(false);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const wantListenRef = useRef(false);
  const interimTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastInterimSentRef = useRef("");

  const clearInterimTimer = useCallback(() => {
    if (interimTimerRef.current) {
      clearTimeout(interimTimerRef.current);
      interimTimerRef.current = null;
    }
  }, []);

  const scheduleInterimTranslate = useCallback(
    (text: string) => {
      clearInterimTimer();
      const trimmed = text.trim();
      if (!trimmed || trimmed.length < 3) {
        setTurkishInterim("");
        return;
      }
      interimTimerRef.current = setTimeout(async () => {
        if (trimmed === lastInterimSentRef.current) return;
        lastInterimSentRef.current = trimmed;
        try {
          const tr = await translateText(trimmed);
          setTurkishInterim(tr);
        } catch {
          /* interim çevirisi sessizce atlanır */
        }
      }, 450);
    },
    [clearInterimTimer],
  );

  const appendFinal = useCallback(
    async (chunk: string) => {
      const text = chunk.trim();
      if (!text) return;
      setEnglishFinal((prev) => (prev ? `${prev} ${text}` : text));
      setEnglishInterim("");
      setTurkishInterim("");
      lastInterimSentRef.current = "";
      setTranslating(true);
      setStatus("Çevriliyor…");
      setStatusKind("");
      try {
        const tr = await translateText(text);
        setTurkishFinal((prev) => (prev ? `${prev} ${tr}` : tr));
        setStatus("Dinleniyor");
        setStatusKind("ok");
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Çeviri başarısız";
        setStatus(msg);
        setStatusKind("error");
      } finally {
        setTranslating(false);
      }
    },
    [],
  );

  const stopListening = useCallback(() => {
    wantListenRef.current = false;
    clearInterimTimer();
    const rec = recognitionRef.current;
    if (rec) {
      try {
        rec.stop();
      } catch {
        /* ignore */
      }
    }
    setListening(false);
    setStatus("Durduruldu");
    setStatusKind("");
  }, [clearInterimTimer]);

  const startListening = useCallback(() => {
    const Ctor = getSpeechRecognition();
    if (!Ctor) {
      setStatus(
        "Bu tarayıcı konuşma tanımayı desteklemiyor. Chrome veya Edge kullanın.",
      );
      setStatusKind("error");
      return;
    }

    wantListenRef.current = true;
    const rec = new Ctor();
    recognitionRef.current = rec;
    rec.lang = "en-US";
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onstart = () => {
      setListening(true);
      setStatus("Dinleniyor — İngilizce konuşun");
      setStatusKind("ok");
    };

    rec.onerror = (ev: Event) => {
      const err = ev as SpeechRecognitionErrorEvent;
      if (err.error === "not-allowed") {
        setStatus("Mikrofon izni verilmedi.");
        setStatusKind("error");
        wantListenRef.current = false;
        setListening(false);
        return;
      }
      if (err.error === "no-speech") {
        setStatus("Ses algılanmadı, tekrar deneyin.");
        setStatusKind("");
        return;
      }
      if (err.error !== "aborted") {
        setStatus(`Tanıma hatası: ${err.error}`);
        setStatusKind("error");
      }
    };

    rec.onend = () => {
      if (wantListenRef.current) {
        try {
          rec.start();
        } catch {
          setListening(false);
        }
        return;
      }
      setListening(false);
    };

    rec.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      let finals = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const piece = event.results[i][0]?.transcript ?? "";
        if (event.results[i].isFinal) {
          finals += piece;
        } else {
          interim += piece;
        }
      }
      if (interim) {
        setEnglishInterim(interim);
        scheduleInterimTranslate(interim);
      }
      if (finals.trim()) {
        void appendFinal(finals);
      }
    };

    try {
      rec.start();
    } catch {
      setStatus("Mikrofon başlatılamadı.");
      setStatusKind("error");
      wantListenRef.current = false;
    }
  }, [appendFinal, scheduleInterimTranslate]);

  useEffect(() => {
    setSupported(!!getSpeechRecognition());
    return () => {
      wantListenRef.current = false;
      clearInterimTimer();
      const rec = recognitionRef.current;
      if (rec) {
        try {
          rec.stop();
        } catch {
          /* ignore */
        }
      }
    };
  }, [clearInterimTimer]);

  const toggleMic = () => {
    if (listening) stopListening();
    else startListening();
  };

  const clearAll = () => {
    setEnglishFinal("");
    setEnglishInterim("");
    setTurkishFinal("");
    setTurkishInterim("");
    lastInterimSentRef.current = "";
    setStatus("");
    setStatusKind("");
  };

  return (
    <main>
      <header>
        <h1>Canlı İngilizce → Türkçe</h1>
        <p>
          Mikrofonunuzdan gelen İngilizce konuşma tanınır ve anlık olarak
          Türkçeye çevrilir.
        </p>
      </header>

      <div className="toolbar">
        <button
          type="button"
          className={`mic${listening ? " listening" : ""}`}
          onClick={toggleMic}
          disabled={supported === false || translating}
          aria-pressed={listening}
        >
          <span className="mic-dot" aria-hidden />
          {listening ? "Durdur" : "Mikrofonu aç"}
        </button>
        <button
          type="button"
          onClick={clearAll}
          style={{
            padding: "12px 18px",
            borderRadius: 999,
            border: "1px solid #243049",
            background: "transparent",
            color: "#c5d0e4",
          }}
        >
          Temizle
        </button>
        {status && (
          <span className={`status${statusKind ? ` ${statusKind}` : ""}`}>
            {status}
          </span>
        )}
      </div>

      <div className="panels">
        <section className="panel" aria-label="İngilizce">
          <div className="panel-head">İngilizce (tanıma)</div>
          <div className="panel-body">
            {englishFinal || (listening ? "…" : "Mikrofonu açın ve konuşun.")}
          </div>
          {(englishInterim || listening) && (
            <div className="panel-body interim">
              {englishInterim || "\u00a0"}
            </div>
          )}
        </section>
        <section className="panel" aria-label="Türkçe">
          <div className="panel-head">Türkçe (çeviri)</div>
          <div className="panel-body">
            {turkishFinal || (listening ? "Çeviri bekleniyor…" : "—")}
          </div>
          {(turkishInterim || englishInterim) && (
            <div className="panel-body interim">{turkishInterim || "\u00a0"}</div>
          )}
        </section>
      </div>

      <p className="hint">
        <strong>İpucu:</strong> En iyi sonuç için Chrome veya Edge kullanın,
        sayfayı <strong>HTTPS</strong> üzerinden açın ve mikrofon izni verin.
        Gürültülü ortamda net konuşmak tanımayı iyileştirir. Çeviri birkaç yüz
        ms gecikmeli güncellenir; bu normaldir.
      </p>
    </main>
  );
}