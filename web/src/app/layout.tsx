import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import Sidebar from "@/components/layout/sidebar"
import "./globals.css"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "VC 투자 분석",
  description: "VC 투자 검토 고도화 시스템",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="ko"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex h-full min-h-screen bg-zinc-50 dark:bg-zinc-950">
        <Sidebar />
        <main className="flex flex-1 flex-col overflow-y-auto p-8">
          {children}
        </main>
      </body>
    </html>
  )
}
