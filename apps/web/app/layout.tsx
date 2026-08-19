import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PII Compliance Agent",
  description: "Detect and mask PII in uploaded documents.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
