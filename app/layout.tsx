import type { Metadata } from "next";
import Script from "next/script";
import { Inter, JetBrains_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/ThemeProvider";
import AppHeader from "@/components/AppHeader";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ICAROS — Lunar Route Optimization",
  description:
    "Intelligent Crater-Aware Route Optimization System for lunar rover path planning",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable}`}>
        <Script id="theme-init" strategy="beforeInteractive">
          {`(function(){try{var t=localStorage.getItem("icaros-theme");var r=t==="dark"||(t!=="light"&&window.matchMedia("(prefers-color-scheme: dark)").matches)?"dark":"light";document.documentElement.dataset.theme=r}catch(e){}})();`}
        </Script>
        <ThemeProvider>
          <AppHeader />
          <main className="app-main">{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
