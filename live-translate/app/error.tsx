"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="tr">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0c1220",
          color: "#e8edf7",
          fontFamily: "system-ui, sans-serif",
          padding: 24,
        }}
      >
        <main style={{ maxWidth: 420, textAlign: "center" }}>
          <h1 style={{ fontSize: "1.25rem" }}>Sayfa yüklenemedi</h1>
          <p style={{ color: "#9aa8c3", fontSize: "0.95rem" }}>
            Beklenmeyen bir hata oluştu. Sayfayı yenileyin veya Chrome / Edge
            kullanın.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: 16,
              padding: "12px 20px",
              borderRadius: 999,
              border: 0,
              background: "#2d7cff",
              color: "#fff",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Tekrar dene
          </button>
        </main>
      </body>
    </html>
  );
}