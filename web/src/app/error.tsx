"use client"

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center px-4">
      <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center dark:border-red-800 dark:bg-red-950">
        <h2 className="mb-2 text-lg font-semibold text-red-800 dark:text-red-300">
          오류가 발생했습니다
        </h2>
        <p className="mb-4 text-sm text-red-600 dark:text-red-400">
          {error.message || "페이지를 표시하는 중 문제가 발생했습니다."}
        </p>
        <button
          onClick={reset}
          className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700"
        >
          다시 시도
        </button>
      </div>
    </div>
  )
}
