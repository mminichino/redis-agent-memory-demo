import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Redis Agent Memory Console",
  description: "Secure chat console powered by gRPC and Redis."
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full min-h-0">{children}</body>
    </html>
  );
}
