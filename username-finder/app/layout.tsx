import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kullanıcı adı arama — Detaylı username finder",
  description:
    "Bir kullanıcı adını birçok sosyal platformda ve web aramasında kontrol edin. Yalnızca herkese açık profiller.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0c1220",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}