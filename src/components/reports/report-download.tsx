"use client"

import { Button } from "@/components/ui/button"

interface ReportDownloadProps {
  markdown: string
  companyName: string
  reportType: string
}

export function ReportDownload({ markdown, companyName, reportType }: ReportDownloadProps) {
  function handleDownload() {
    const timestamp = new Date().toISOString().slice(0, 10)
    const filename = `${companyName}_${reportType}_${timestamp}.md`
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Button variant="secondary" onClick={handleDownload} disabled={!markdown}>
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      MD 다운로드
    </Button>
  )
}
