"use client"

import { useState, useRef, useCallback } from "react"
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

  // 리포트 저장
  const [outputDir, setOutputDir] = useState("")
  const serverOutputDir = process.env.NEXT_PUBLIC_DEFAULT_OUTPUT || ""

  // 파일 탐색기
  const [irBrowseOpen, setIrBrowseOpen] = useState(false)
  const [outputBrowseOpen, setOutputBrowseOpen] = useState(false)

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
          // 업로드하면 항상 업로드 경로를 IR 경로로 설정
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
    const effectiveOutputDir = outputDir.trim() || serverOutputDir

    if (!company.trim() || !effectiveIrDir || !effectiveOutputDir) return

    setRunning(true)
    setLogs([])
    setDone(null)
    setReportFiles([])

    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company: company.trim(),
          irDir: effectiveIrDir,
          outputDir: effectiveOutputDir,
          reportType,
          options: { noWeb, noApi },
        }),
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
                loadReportFiles(effectiveOutputDir)
              }
            }
            setTimeout(scrollToBottom, 50)
          } catch {
            // skip
          }
        }
      }
    } catch (err) {
      setLogs((prev) => [
        ...prev,
        { type: "error", message: `네트워크 오류: ${err}` },
      ])
    } finally {
      setRunning(false)
    }
  }

  const loadReportFiles = async (dir: string) => {
    try {
      const res = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ directory: dir }),
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
  const isOutputReady = outputDir.trim().length > 0
  const isValid = company.trim() && isSourceReady && isOutputReady

  return (
    <div className="mx-auto w-full max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
        투자 분석 실행
      </h1>
      <p className="mb-8 text-sm text-zinc-500">
        IR 자료를 기반으로 투자검토보고서 및 투심위보고서를 생성합니다.
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
              // 기업명 변경 시 이전 업로드 상태 초기화
              setUploadedFiles([])
              setUploadDir("")
              setIrDir("")
            }}
            placeholder="예: Pixxel"
            disabled={running}
            className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </div>

        {/* ─── IR 자료 소스 ─── */}
        <div>
          <label className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            IR 자료 소스 <span className="text-red-500">*</span>
          </label>

          {/* 탐색기로 선택 */}
          <div className="flex gap-2">
            <div
              className={`flex flex-1 items-center rounded-md border px-3 py-2 ${
                irDir
                  ? "border-zinc-300 dark:border-zinc-700"
                  : "border-dashed border-zinc-300 dark:border-zinc-700"
              } bg-white dark:bg-zinc-800`}
            >
              {irDir ? (
                <div className="flex flex-1 items-center justify-between">
                  <span className="truncate font-mono text-sm text-zinc-900 dark:text-zinc-100">
                    {irDir}
                  </span>
                  <button
                    type="button"
                    onClick={() => { setIrDir(""); setUploadedFiles([]); setUploadDir("") }}
                    className="ml-2 shrink-0 text-zinc-400 hover:text-zinc-600"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ) : (
                <span className="text-sm text-zinc-400">탐색기로 폴더를 선택하거나 아래에서 파일을 업로드하세요</span>
              )}
            </div>
            <button
              type="button"
              onClick={() => setIrBrowseOpen(true)}
              disabled={running}
              className="flex shrink-0 items-center gap-1.5 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
            >
              <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
              </svg>
              찾아보기
            </button>
          </div>

          {/* 또는 파일 업로드 */}
          <div className="mt-3">
            <div
              onClick={() => !running && company.trim() && fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); e.stopPropagation() }}
              onDrop={(e) => {
                e.preventDefault(); e.stopPropagation()
                if (!running && company.trim()) handleFileUpload(e.dataTransfer.files)
              }}
              className={`flex min-h-[72px] cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed transition-colors ${
                !company.trim()
                  ? "border-zinc-200 bg-zinc-50 opacity-50 dark:border-zinc-800 dark:bg-zinc-900"
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
                <p className="text-sm text-zinc-500">
                  {company.trim()
                    ? "또는 여기를 클릭/드래그하여 PC에서 직접 업로드 (PDF, PPT, Excel, Word, HWP)"
                    : "기업명을 먼저 입력하세요"}
                </p>
              )}
            </div>

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
              </div>
            )}
          </div>
        </div>

        {/* ─── 리포트 저장 ─── */}
        <div>
          <label className="mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            리포트 저장 위치 <span className="text-red-500">*</span>
          </label>

          {/* 탐색기로 선택 */}
          <div className="flex gap-2">
            <div
              className={`flex flex-1 items-center rounded-md border px-3 py-2 ${
                outputDir
                  ? "border-zinc-300 dark:border-zinc-700"
                  : "border-dashed border-zinc-300 dark:border-zinc-700"
              } bg-white dark:bg-zinc-800`}
            >
              {outputDir ? (
                <div className="flex flex-1 items-center justify-between">
                  <span className="truncate font-mono text-sm text-zinc-900 dark:text-zinc-100">
                    {outputDir}
                  </span>
                  <button
                    type="button"
                    onClick={() => setOutputDir("")}
                    className="ml-2 shrink-0 text-zinc-400 hover:text-zinc-600"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ) : (
                <span className="text-sm text-zinc-400">탐색기로 저장 폴더를 선택하세요</span>
              )}
            </div>
            <button
              type="button"
              onClick={() => setOutputBrowseOpen(true)}
              disabled={running}
              className="flex shrink-0 items-center gap-1.5 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
            >
              <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
              </svg>
              찾아보기
            </button>
          </div>
          <p className="mt-1 text-xs text-zinc-400">
            생성된 Word 보고서(.docx)가 저장될 폴더
          </p>
        </div>

        {/* ─── 보고서 유형 ─── */}
        <div>
          <label className="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
            보고서 유형 <span className="text-red-500">*</span>
          </label>
          <div className="grid grid-cols-2 gap-3">
            {([
              { value: "investment" as const, label: "투자검토보고서", desc: "Gate1 스크리닝 기반 검토 보고서" },
              { value: "ic" as const, label: "투심위보고서", desc: "투자심의위원회 10-Part 보고서" },
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

      {/* ─── 리포트 다운로드 ─── */}
      {reportFiles.length > 0 && (
        <div className="mt-6">
          <h2 className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
            생성된 리포트
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
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m.75 12l3 3m0 0l3-3m-3 3v-6m-1.5-9H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
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
                  다운로드
                </span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* ─── 파일 탐색기 모달 ─── */}
      <FileBrowser
        open={irBrowseOpen}
        onClose={() => setIrBrowseOpen(false)}
        onSelect={(path) => setIrDir(path)}
        mode="directory"
        title="IR 자료 폴더 선택"
      />
      <FileBrowser
        open={outputBrowseOpen}
        onClose={() => setOutputBrowseOpen(false)}
        onSelect={(path) => setOutputDir(path)}
        mode="directory"
        title="리포트 저장 폴더 선택"
      />
    </div>
  )
}
