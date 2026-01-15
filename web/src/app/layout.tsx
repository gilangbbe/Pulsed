import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pulsed - AI & ML News Digest",
  description: "Get curated AI and Machine Learning news delivered to your inbox daily.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
