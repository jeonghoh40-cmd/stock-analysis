"use client"

import { useState } from "react"
import { Download, FileText } from "lucide-react"
import { Button } from "@/components/ui/button"

interface ReportDownloadProps {
  markdown: string
  companyName: string
  reportType: string
}

export function ReportDownload({ markdown, companyName, reportType }: ReportDownloadProps) {
  const [downloading, setDownloading] = useState<"md" | "docx" | null>(null)
  const [error, setError] = useState<string | null>(null)

  function buildFilename(): string {
    const timestamp = new Date().toISOString().slice(0, 10)
    return `${companyName}_${reportType}_${timestamp}`
  }

  function handleMarkdownDownload() {
    setDownloading("md")
    setError(null)
    try {
      const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${buildFilename()}.md`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(null)
    }
  }

  async function handleDocxDownload() {
    setDownloading("docx")
    setError(null)
    try {
      const filename = buildFilename()
      const res = await fetch("/api/convert-docx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markdown, filename }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.error || `변환 실패 (${res.status})`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${filename}.docx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : "DOCX 변환 중 오류가 발생했습니다.")
    } finally {
      setDownloading(null)
    }
  }

  const disabled = !markdown || downloading !== null

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <Button variant="secondary" onClick={handleMarkdownDownload} disabled={disabled}>
          <FileText className="h-4 w-4" strokeWidth={2} />
          {downloading === "md" ? "다운로드 중..." : "MD 다운로드"}
        </Button>
        <Button variant="secondary" onClick={handleDocxDownload} disabled={disabled}>
          <Download className="h-4 w-4" strokeWidth={2} />
          {downloading === "docx" ? "변환 중..." : "DOCX 다운로드"}
        </Button>
      </div>
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  )
}
