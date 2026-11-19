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

function cancelBrowserSpeech() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

function pickTurkishVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    return null;
  }
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((v) => v.lang === "tr-TR" || v.lang.startsWith("tr-")) ??
    voices.find((v) => /turk/i.test(v.name)) ??
    null
  );
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
  const [turkishLines, setTurkishLines] = useState<string[]>([]);
  const [turkishInterim, setTurkishInterim] = useState("");
  const [translating, setTranslating] = useState(false);
  const [speakEnabled, setSpeakEnabled] = useState(false);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const wantListenRef = useRef(false);
  const interimTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastInterimSentRef = useRef("");
  const speakEnabledRef = useRef(false);
  const speakQueueRef = useRef<string[]>([]);
  const speakingRef = useRef(false);
  const lastSpokenRef = useRef("");

  const flushSpeakQueue = useCallback(() => {
    if (
      typeof window === "undefined" ||
      !speakEnabledRef.current ||
      speakingRef.current ||
      !("speechSynthesis" in window)
    ) {
      return;
    }
    const next = speakQueueRef.current.shift();
    if (!next) return;
    speakingRef.current = true;
    const utterance = new SpeechSynthesisUtterance(next);
    utterance.lang = "tr-TR";
    const voice = pickTurkishVoice();
    if (voice) utterance.voice = voice;
    utterance.rate = 0.96;
    utterance.onend = () => {
      speakingRef.current = false;
      flushSpeakQueue();
    };
    utterance.onerror = () => {
      speakingRef.current = false;
      flushSpeakQueue();
    };
    try {
      window.speechSynthesis.speak(utterance);
    } catch {
      speakingRef.current = false;
      flushSpeakQueue();
    }
  }, []);

  const enqueueTurkishSpeech = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!speakEnabledRef.current || !trimmed || trimmed === lastSpokenRef.current) {
        return;
      }
      lastSpokenRef.current = trimmed;
      speakQueueRef.current.push(trimmed);
      flushSpeakQueue();
    },
    [flushSpeakQueue],
  );

  const stopTurkishSpeech = useCallback(() => {
    speakQueueRef.current = [];
    speakingRef.current = false;
    lastSpokenRef.current = "";
    cancelBrowserSpeech();
  }, []);

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
        setTurkishLines((prev) => [...prev, tr].slice(-4));
        setTurkishInterim("");
        enqueueTurkishSpeech(tr);
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
    [enqueueTurkishSpeech],
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
    try {
      const stored = localStorage.getItem("live-tr-speak");
      if (stored === "1") setSpeakEnabled(true);
    } catch {
      /* ignore */
    }
    return () => {
      wantListenRef.current = false;
      clearInterimTimer();
      stopTurkishSpeech();
      const rec = recognitionRef.current;
      if (rec) {
        try {
          rec.stop();
        } catch {
          /* ignore */
        }
      }
    };
  }, [clearInterimTimer, stopTurkishSpeech]);

  useEffect(() => {
    speakEnabledRef.current = speakEnabled;
    try {
      localStorage.setItem("live-tr-speak", speakEnabled ? "1" : "0");
    } catch {
      /* ignore */
    }
    if (!speakEnabled) {
      stopTurkishSpeech();
    }
  }, [speakEnabled, stopTurkishSpeech]);

  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;
    const warmVoices = () => {
      try {
        synth.getVoices();
      } catch {
        /* ignore */
      }
    };
    warmVoices();
    const previous = synth.onvoiceschanged;
    synth.onvoiceschanged = warmVoices;
    return () => {
      synth.onvoiceschanged = previous ?? null;
    };
  }, []);

  const toggleMic = () => {
    if (listening) stopListening();
    else startListening();
  };

  const clearAll = () => {
    setEnglishFinal("");
    setEnglishInterim("");
    setTurkishLines([]);
    setTurkishInterim("");
    stopTurkishSpeech();
    lastInterimSentRef.current = "";
    setStatus("");
    setStatusKind("");
  };

  const lastFinalLine = turkishLines[turkishLines.length - 1];
  const previousFinalLine = turkishLines[turkishLines.length - 2];
  const mainSubtitle = turkishInterim || lastFinalLine || "";
  const dimSubtitle = turkishInterim
    ? lastFinalLine
    : previousFinalLine;

  return (
    <main>
      <header>
        <h1>Canlı Türkçe altyazı</h1>
        <p>
          İngilizce konuşma mikrofondan tanınır; Türkçe altyazı ekranda
          görünür. İsterseniz çeviriyi sesli de okutabilirsiniz.
        </p>
        <span className="badge-muted">
          {speakEnabled
            ? "Sesli okuma açık — kesinleşen cümleler okunur"
            : "Varsayılan: yalnızca yazı altyazı"}
        </span>
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
        <button
          type="button"
          className={`speak-toggle${speakEnabled ? " on" : ""}`}
          onClick={() => setSpeakEnabled((v) => !v)}
          aria-pressed={speakEnabled}
        >
          <span className="speak-toggle-knob" aria-hidden />
          Sesli okuma: {speakEnabled ? "Açık" : "Kapalı"}
        </button>
        {status && (
          <span className={`status${statusKind ? ` ${statusKind}` : ""}`}>
            {status}
          </span>
        )}
      </div>

      <section
        className="subtitle-stage"
        aria-label="Türkçe altyazı"
        aria-live="off"
      >
        <span className="subtitle-label">Altyazı</span>
        {!mainSubtitle ? (
          <p className="subtitle-empty">
            {listening
              ? "Konuşun, Türkçe altyazı burada görünecek…"
              : "Mikrofonu açıp İngilizce konuşun."}
          </p>
        ) : (
          <>
            {dimSubtitle && dimSubtitle !== mainSubtitle ? (
              <p className="subtitle-line dim">{dimSubtitle}</p>
            ) : null}
            <p
              className={`subtitle-line${
                turkishInterim ? " interim" : ""
              }`}
            >
              {mainSubtitle}
            </p>
          </>
        )}
      </section>

      <details className="details-en">
        <summary>İngilizce tanıma metni (isteğe bağlı)</summary>
        <div className="details-en-body">
          {englishFinal || "—"}
          {englishInterim ? (
            <div className="interim">{englishInterim}</div>
          ) : null}
        </div>
      </details>

      <p className="hint">
        <strong>İpucu:</strong> Chrome veya Edge kullanın; mikrofon izni verin.
        <strong>Sesli okuma</strong> kapalıyken yalnızca altyazı gösterilir;
        açıkken tanımanın kesinleştiği Türkçe cümleler tarayıcı sesiyle okunur
        (sırada bekletilir). Çeviri birkaç yüz ms gecikmeli olabilir.
      </p>
    </main>
  );
}