import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { themeBootstrapScript } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Clothist — AI-native fashion discovery",
  description:
    "Search across retailers. Type what you're picturing. Faster, smarter clothing discovery.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrapScript }} />
      </head>
      <body className="bg-background text-foreground">
        <div className="grain" aria-hidden />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
