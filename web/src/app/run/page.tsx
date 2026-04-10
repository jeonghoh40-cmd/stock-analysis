"use client"

import { useState, useRef, useCallback, useEffect } from "react"
import FileBrowser from "@/components/ui/file-browser"

type LogEntry = {
  type: "info" | "stdout" | "stderr" | "done" | "error"
  message: string
  exitCode?: number | null
}

type ReportFile = {
  name: string
  path: string
  size: number
  modified: string
}

export default function RunPage() {
  const [company, setCompany] = useState("")

  // IR 소스
  const [irDir, setIrDir] = useState("")
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([])
  const [uploadDir, setUploadDir] = useState("")
  const [uploading, setUploading] = useState(false)

  // 파일 탐색기 (사내 네트워크 전용)
  const [irBrowseOpen, setIrBrowseOpen] = useState(false)

  // 보고서 유형
  const [reportType, setReportType] = useState<"investment" | "ic">("investment")

  // 옵션
  const [noWeb, setNoWeb] = useState(false)
  const [noApi, setNoApi] = useState(false)

  // 실행 상태
  const [running, setRunning] = useState(false)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [done, setDone] = useState<boolean | null>(null)
  const [reportFiles, setReportFiles] = useState<ReportFile[]>([])
  const logEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const runAbortRef = useRef<AbortController | null>(null)

  // 페이지 unmount 시 진행 중인 SSE 스트림/업로드 중단
  useEffect(() => {
    return () => runAbortRef.current?.abort()
  }, [])

  const scrollToBottom = () => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  // 파일 업로드
  const handleFileUpload = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0 || !company.trim()) return
      setUploading(true)
      const formData = new FormData()
      formData.append("company", company.trim())
      for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i])
      }
      try {
        const res = await fetch("/api/upload", { method: "POST", body: formData })
        const data = await res.json()
        if (res.ok) {
          setUploadedFiles(data.files)
          setUploadDir(data.uploadDir)
          setIrDir(data.uploadDir)
        }
      } catch (err) {
        console.error("업로드 실패:", err)
      } finally {
        setUploading(false)
        if (fileInputRef.current) fileInputRef.current.value = ""
      }
    },
    [company]
  )

  // 분석 실행
  const handleRun = async () => {
    const effectiveIrDir = irDir.trim() || uploadDir

    if (!company.trim() || !effectiveIrDir) return

    setRunning(true)
    setLogs([])
    setDone(null)
    setReportFiles([])

    const controller = new AbortController()
    runAbortRef.current = controller

    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company: company.trim(),
          irDir: effectiveIrDir,
          reportType,
          options: { noWeb, noApi },
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.json()
        setLogs([{ type: "error", message: err.error || "요청 실패" }])
        setRunning(false)
        return
      }

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        setLogs([{ type: "error", message: "스트림을 열 수 없습니다." }])
        setRunning(false)
        return
      }

      let buffer = ""
      while (true) {
        const { done: readerDone, value } = await reader.read()
        if (readerDone) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          try {
            const entry: LogEntry = JSON.parse(line.slice(6))
            setLogs((prev) => [...prev, entry])
            if (entry.type === "done") {
              setDone(entry.exitCode === 0)
              if (entry.exitCode === 0) {
                loadReportFiles()
              }
            }
            setTimeout(scrollToBottom, 50)
          } catch {
            // skip
          }
        }
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setLogs((prev) => [...prev, { type: "info", message: "사용자가 중단했습니다." }])
      } else {
        setLogs((prev) => [
          ...prev,
          { type: "error", message: `네트워크 오류: ${err}` },
        ])
      }
    } finally {
      setRunning(false)
      runAbortRef.current = null
    }
  }

  const loadReportFiles = async () => {
    try {
      const res = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company: company.trim(), reportType }),
      })
      const data = await res.json()
      if (data.files) setReportFiles(data.files)
    } catch {
      // ignore
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const isSourceReady = irDir.trim().length > 0 || uploadedFiles.length > 0
  const isValid = company.trim() && isSourceReady

  return (
    <div className="mx-auto w-full max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
        투자 분석 실행
      </h1>
      <p className="mb-8 text-sm text-zinc-500">
        IR/IM 자료를 업로드하면 보고서를 생성하여 다운로드할 수 있습니다.
      </p>

      <div className="space-y-6 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        {/* ─── 기업명 ─── */}
        <div>
          <label className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            기업명 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={company}
            onChange={(e) => {
              setCompany(e.target.value)
              setUploadedFiles([])
              setUploadDir("")
              setIrDir("")
            }}
            placeholder="예: Pixxel"
            disabled={running}
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </div>

        {/* ─── IR/IM 자료 ─── */}
        <div>
          <label className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            IR/IM 자료 <span className="text-red-500">*</span>
          </label>

          {/* 파일 업로드 영역 */}
          <div
            onClick={() => !running && company.trim() && fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation() }}
            onDrop={(e) => {
              e.preventDefault(); e.stopPropagation()
              if (!running && company.trim()) handleFileUpload(e.dataTransfer.files)
            }}
            className={`flex min-h-[80px] cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed transition-colors ${
              !company.trim()
                ? "border-zinc-200 bg-zinc-50 opacity-50 dark:border-zinc-800 dark:bg-zinc-900"
                : uploadedFiles.length > 0
                  ? "border-green-300 bg-green-50/50 hover:border-green-400 dark:border-green-700 dark:bg-green-900/20"
                  : "border-zinc-300 bg-zinc-50 hover:border-blue-400 dark:border-zinc-700 dark:bg-zinc-800/50"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.pptx,.ppt,.xlsx,.xls,.docx,.doc,.hwp,.hwpx,.txt,.md"
              onChange={(e) => handleFileUpload(e.target.files)}
              className="hidden"
            />
            {uploading ? (
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                업로드 중...
              </div>
            ) : (
              <>
                <svg className="mb-1 h-6 w-6 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
                <p className="text-sm text-zinc-500">
                  {company.trim()
                    ? "클릭하거나 파일을 드래그하여 업로드 (PDF, PPT, Excel, Word, HWP)"
                    : "기업명을 먼저 입력하세요"}
                </p>
              </>
            )}
          </div>

          {/* 업로드된 파일 목록 */}
          {uploadedFiles.length > 0 && (
            <div className="mt-2 space-y-1">
              {uploadedFiles.map((name, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded bg-zinc-100 px-2.5 py-1.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                >
                  <svg className="h-3.5 w-3.5 shrink-0 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  {name}
                </div>
              ))}
              <button
                type="button"
                onClick={() => { setUploadedFiles([]); setUploadDir(""); setIrDir("") }}
                className="mt-1 text-xs text-zinc-400 hover:text-red-500"
              >
                파일 초기화
              </button>
            </div>
          )}

          {/* 사내 네트워크용 찾아보기 (서버 디렉토리) */}
          {!uploadedFiles.length && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-xs text-zinc-400">또는</span>
              <button
                type="button"
                onClick={() => setIrBrowseOpen(true)}
                disabled={running}
                className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50"
              >
                <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                </svg>
                서버/네트워크 폴더에서 선택 (사내 전용)
              </button>
            </div>
          )}

          {/* irDir이 설정되었지만 업로드가 아닌 경우 (찾아보기로 선택) */}
          {irDir && !uploadedFiles.length && (
            <div className="mt-2 flex items-center gap-2 rounded bg-zinc-100 px-2.5 py-1.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
              <svg className="h-3.5 w-3.5 shrink-0 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
              </svg>
              <span className="flex-1 truncate font-mono">{irDir}</span>
              <button
                type="button"
                onClick={() => setIrDir("")}
                className="shrink-0 text-zinc-400 hover:text-red-500"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* ─── 보고서 유형 ─── */}
        <div>
          <label className="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            보고서 유형 <span className="text-red-500">*</span>
          </label>
          <div className="grid grid-cols-2 gap-3">
            {([
              { value: "investment" as const, label: "투자검토보고서", desc: "Gate1 스크리닝 기반 검토 보고서" },
              { value: "ic" as const, label: "투심위보고서", desc: "투자심의위원회 보고서" },
            ]).map((opt) => (
              <label
                key={opt.value}
                className={`flex cursor-pointer flex-col rounded-lg border-2 p-3 transition-colors ${
                  reportType === opt.value
                    ? "border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950/30"
                    : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-700 dark:hover:border-zinc-600"
                } ${running ? "pointer-events-none opacity-50" : ""}`}
              >
                <input
                  type="radio"
                  name="reportType"
                  value={opt.value}
                  checked={reportType === opt.value}
                  onChange={() => setReportType(opt.value)}
                  disabled={running}
                  className="sr-only"
                />
                <span className={`text-sm font-medium ${
                  reportType === opt.value
                    ? "text-blue-700 dark:text-blue-300"
                    : "text-zinc-700 dark:text-zinc-300"
                }`}>
                  {opt.label}
                </span>
                <span className="mt-0.5 text-xs text-zinc-400">{opt.desc}</span>
              </label>
            ))}
          </div>
        </div>

        {/* ─── 옵션 ─── */}
        <div>
          <label className="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            옵션
          </label>
          <div className="flex gap-6">
            <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <input
                type="checkbox"
                checked={noWeb}
                onChange={(e) => setNoWeb(e.target.checked)}
                disabled={running}
                className="rounded border-zinc-300 dark:border-zinc-600"
              />
              웹 조사 건너뛰기
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <input
                type="checkbox"
                checked={noApi}
                onChange={(e) => setNoApi(e.target.checked)}
                disabled={running}
                className="rounded border-zinc-300 dark:border-zinc-600"
              />
              API 없이 기존 데이터만 사용
            </label>
          </div>
        </div>

        {/* ─── 실행 버튼 ─── */}
        <button
          onClick={handleRun}
          disabled={!isValid || running}
          className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running ? (
            <>
              <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              실행 중...
            </>
          ) : (
            <>
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {reportType === "investment"
                ? "투자검토보고서 생성"
                : "투심위보고서 생성"}
            </>
          )}
        </button>
      </div>

      {/* ─── 실행 로그 ─── */}
      {logs.length > 0 && (
        <div className="mt-6">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              실행 로그
            </h2>
            {done !== null && (
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  done
                    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                    : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                }`}
              >
                {done ? "성공" : "실패"}
              </span>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto rounded-lg border border-zinc-200 bg-zinc-950 p-4 font-mono text-xs leading-relaxed dark:border-zinc-800">
            {logs.map((log, i) => (
              <div
                key={i}
                className={
                  log.type === "error" || log.type === "stderr"
                    ? "text-red-400"
                    : log.type === "done"
                      ? "text-green-400"
                      : log.type === "info"
                        ? "text-blue-400"
                        : "text-zinc-300"
                }
              >
                {log.message}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {/* ─── 보고서 다운로드 ─── */}
      {reportFiles.length > 0 && (
        <div className="mt-6">
          <h2 className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
            생성된 보고서 — 클릭하여 내 PC에 저장
          </h2>
          <div className="space-y-2">
            {reportFiles.map((file) => (
              <a
                key={file.path}
                href={`/api/download?path=${encodeURIComponent(file.path)}`}
                download
                className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white px-4 py-3 transition-colors hover:border-blue-300 hover:bg-blue-50 dark:border-zinc-700 dark:bg-zinc-800 dark:hover:border-blue-600 dark:hover:bg-zinc-700"
              >
                <div className="flex items-center gap-3">
                  <svg className="h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {file.name}
                    </p>
                    <p className="text-xs text-zinc-400">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                </div>
                <span className="text-xs font-medium text-blue-600 dark:text-blue-400">
                  내 PC에 저장
                </span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* ─── 파일 탐색기 모달 (사내 전용) ─── */}
      <FileBrowser
        open={irBrowseOpen}
        onClose={() => setIrBrowseOpen(false)}
        onSelect={(path) => { setIrDir(path); setUploadedFiles([]) }}
        mode="directory"
        title="서버/네트워크 폴더 선택 (사내 전용)"
      />
    </div>
  )
}
