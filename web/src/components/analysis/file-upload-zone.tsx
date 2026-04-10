"use client"

import { useCallback, useState } from "react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Spinner } from "@/components/ui/spinner"
import { uploadAndExtract } from "@/lib/api"
import type { ExtractedFile } from "@/lib/types"

interface FileUploadZoneProps {
  onExtracted: (combinedText: string, files: ExtractedFile[]) => void
}

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]

const ACCEPTED_EXTENSIONS = [".pdf", ".pptx", ".docx"]

export default function FileUploadZone({ onExtracted }: FileUploadZoneProps) {
  const [files, setFiles] = useState<File[]>([])
  const [extractedFiles, setExtractedFiles] = useState<ExtractedFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const valid = Array.from(newFiles).filter(
      (f) =>
        ACCEPTED_TYPES.includes(f.type) ||
        ACCEPTED_EXTENSIONS.some((ext) => f.name.toLowerCase().endsWith(ext))
    )
    if (valid.length === 0) {
      setError("지원하지 않는 파일 형식입니다. PDF, PPTX, DOCX만 가능합니다.")
      return
    }
    setError(null)
    setFiles((prev) => [...prev, ...valid])
  }, [])

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      if (e.dataTransfer.files.length > 0) {
        addFiles(e.dataTransfer.files)
      }
    },
    [addFiles]
  )

  const handleUpload = async () => {
    if (files.length === 0) return
    setUploading(true)
    setProgress(0)
    setError(null)

    try {
      const result = await uploadAndExtract(files, setProgress)
      setExtractedFiles(result.files)
      onExtracted(result.combined_text, result.files)
    } catch (err) {
      setError(err instanceof Error ? err.message : "업로드 중 오류가 발생했습니다.")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* 드래그앤드롭 영역 */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-12 transition-colors",
          dragOver
            ? "border-blue-400 bg-blue-50 dark:border-blue-500 dark:bg-blue-950/30"
            : "border-zinc-300 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900"
        )}
      >
        <svg
          className="mb-4 h-12 w-12 text-zinc-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
        <p className="mb-2 text-sm text-zinc-600 dark:text-zinc-400">
          IR자료, IM자료, 재무자료를 드래그하여 업로드하세요
        </p>
        <p className="mb-4 text-xs text-zinc-400">PDF, PPTX, DOCX 지원</p>
        <label className="cursor-pointer rounded-lg bg-white px-4 py-2 text-sm font-medium text-zinc-700 shadow-sm ring-1 ring-zinc-300 transition-colors hover:bg-zinc-50 dark:bg-zinc-800 dark:text-zinc-200 dark:ring-zinc-600">
          파일 선택
          <input
            type="file"
            multiple
            accept=".pdf,.pptx,.docx"
            className="hidden"
            onChange={(e) => e.target.files && addFiles(e.target.files)}
          />
        </label>
      </div>

      {/* 에러 */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {/* 파일 목록 */}
      {files.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            업로드할 파일 ({files.length}개)
          </h3>
          {files.map((f, i) => {
            const extracted = extractedFiles.find((ef) => ef.filename === f.name)
            return (
              <div
                key={`${f.name}-${i}`}
                className="flex items-center justify-between rounded-md border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-700 dark:bg-zinc-800"
              >
                <div className="flex items-center gap-3">
                  <svg
                    className="h-5 w-5 text-zinc-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {f.name}
                    </p>
                    <p className="text-xs text-zinc-400">
                      {(f.size / 1024).toFixed(0)} KB
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {extracted && (
                    <Badge
                      variant={extracted.status === "success" ? "success" : "error"}
                    >
                      {extracted.status === "success"
                        ? `${extracted.char_count.toLocaleString()}자 추출`
                        : "추출 실패"}
                    </Badge>
                  )}
                  {!uploading && (
                    <button
                      type="button"
                      onClick={() => removeFile(i)}
                      className="text-zinc-400 hover:text-red-500"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            )
          })}

          {/* 업로드 버튼 / 진행률 */}
          {uploading ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Spinner className="h-4 w-4" />
                <span className="text-sm text-zinc-600 dark:text-zinc-400">
                  텍스트 추출 중... {progress}%
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          ) : (
            extractedFiles.length === 0 && (
              <button
                type="button"
                onClick={handleUpload}
                className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
              >
                텍스트 추출 시작
              </button>
            )
          )}
        </div>
      )}
    </div>
  )
}
