"use client"

import { useState, useEffect, useCallback } from "react"

type EntryInfo = {
  name: string
  path: string
  isDir: boolean
  size: number
  modified: string
}

type BrowseResponse = {
  entries: EntryInfo[]
  currentPath: string
  parentPath: string | null
  error?: string
}

type FileBrowserProps = {
  open: boolean
  onClose: () => void
  onSelect: (path: string) => void
  mode: "directory" | "file"
  title?: string
  fileFilter?: string[]
}

export default function FileBrowser({
  open,
  onClose,
  onSelect,
  mode,
  title,
  fileFilter,
}: FileBrowserProps) {
  const [currentPath, setCurrentPath] = useState("")
  const [parentPath, setParentPath] = useState<string | null>(null)
  const [entries, setEntries] = useState<EntryInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [manualPath, setManualPath] = useState("")

  const browse = useCallback(async (dirPath: string) => {
    setLoading(true)
    setError("")
    try {
      const res = await fetch("/api/browse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dirPath: dirPath || null }),
      })
      const data: BrowseResponse = await res.json()
      if (data.error) {
        setError(data.error)
      } else {
        setEntries(data.entries)
        setCurrentPath(data.currentPath)
        setParentPath(data.parentPath)
        setManualPath(data.currentPath)
      }
    } catch {
      setError("서버에 연결할 수 없습니다.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      browse("")
    }
  }, [open, browse])

  if (!open) return null

  const handleEntryClick = (entry: EntryInfo) => {
    if (entry.isDir) {
      browse(entry.path)
    } else if (mode === "file") {
      onSelect(entry.path)
      onClose()
    }
  }

  const handleSelectCurrent = () => {
    if (currentPath) {
      onSelect(currentPath)
      onClose()
    }
  }

  const handleManualGo = () => {
    if (manualPath.trim()) {
      browse(manualPath.trim())
    }
  }

  const filteredEntries =
    mode === "directory"
      ? entries.filter((e) => e.isDir)
      : fileFilter
        ? entries.filter(
            (e) =>
              e.isDir ||
              fileFilter.some((ext) => e.name.toLowerCase().endsWith(ext))
          )
        : entries

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-lg border border-zinc-200 bg-white shadow-xl dark:border-zinc-700 dark:bg-zinc-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-700">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {title || (mode === "directory" ? "폴더 선택" : "파일 선택")}
          </h3>
          <button
            onClick={onClose}
            className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Path bar */}
        <div className="flex gap-2 border-b border-zinc-200 px-4 py-2 dark:border-zinc-700">
          <input
            type="text"
            value={manualPath}
            onChange={(e) => setManualPath(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleManualGo()}
            placeholder="경로 직접 입력..."
            className="flex-1 rounded border border-zinc-300 px-2 py-1 font-mono text-xs text-zinc-900 focus:border-blue-500 focus:outline-none dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <button
            onClick={handleManualGo}
            className="rounded bg-zinc-200 px-3 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-600"
          >
            이동
          </button>
        </div>

        {/* Entries */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-sm text-zinc-400">
              <svg className="mr-2 h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              로딩 중...
            </div>
          ) : error ? (
            <div className="px-4 py-8 text-center text-sm text-red-500">{error}</div>
          ) : (
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
              {/* 상위 폴더 */}
              {parentPath && (
                <button
                  onClick={() => browse(parentPath)}
                  className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-800"
                >
                  <svg className="h-4 w-4 shrink-0 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                  <span className="text-zinc-500">..</span>
                  <span className="text-xs text-zinc-400">상위 폴더</span>
                </button>
              )}

              {filteredEntries.length === 0 && !parentPath && (
                <div className="px-4 py-8 text-center text-sm text-zinc-400">
                  항목이 없습니다
                </div>
              )}

              {filteredEntries.map((entry) => (
                <button
                  key={entry.path}
                  onClick={() => handleEntryClick(entry)}
                  className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-800"
                >
                  {entry.isDir ? (
                    <svg className="h-4 w-4 shrink-0 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
                    </svg>
                  ) : (
                    <svg className="h-4 w-4 shrink-0 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                  )}
                  <span className="flex-1 truncate text-zinc-900 dark:text-zinc-100">
                    {entry.name}
                  </span>
                  {!entry.isDir && entry.size > 0 && (
                    <span className="text-xs text-zinc-400">
                      {entry.size < 1024 * 1024
                        ? `${(entry.size / 1024).toFixed(0)} KB`
                        : `${(entry.size / (1024 * 1024)).toFixed(1)} MB`}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-zinc-200 px-4 py-3 dark:border-zinc-700">
          <div className="max-w-sm truncate font-mono text-xs text-zinc-400">
            {currentPath || "루트"}
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-md border border-zinc-300 px-4 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50 dark:border-zinc-600 dark:text-zinc-400 dark:hover:bg-zinc-800"
            >
              취소
            </button>
            {mode === "directory" && currentPath && (
              <button
                onClick={handleSelectCurrent}
                className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
              >
                이 폴더 선택
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
