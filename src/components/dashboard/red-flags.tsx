"use client"

import type { RedFlagItem } from "@/lib/types"

export function RedFlags({ flags }: { flags: RedFlagItem[] }) {
  const triggered = flags.filter((f) => f.triggered)

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="mb-4 text-sm font-medium text-zinc-500 dark:text-zinc-400">Red Flags</h2>
      {triggered.length === 0 ? (
        <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
          Red Flag 없음
        </span>
      ) : (
        <ul className="space-y-3">
          {triggered.map((f) => (
            <li key={f.flag} className="rounded-md border border-red-200 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950/20">
              <p className="text-sm font-semibold text-red-800 dark:text-red-400">{f.name}</p>
              <p className="mt-1 text-sm text-red-700 dark:text-red-300">{f.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
