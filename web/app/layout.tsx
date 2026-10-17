import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Archivo, JetBrains_Mono } from "next/font/google";

import "./theme.css";

const archivo = Archivo({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800", "900"],
  variable: "--font-archivo",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "Playbook",
  description: "AI-driven discovery for finance & accounting.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${archivo.variable} ${jetbrainsMono.variable}`}>
      <body
        style={{
          // next/font self-hosts the files; point the theme tokens at them.
          ["--font-display" as string]: `var(--font-archivo), "Helvetica Neue", Arial, sans-serif`,
          ["--font-mono" as string]: `var(--font-jetbrains), ui-monospace, monospace`,
        }}
      >
        {children}
      </body>
    </html>
  );
}
