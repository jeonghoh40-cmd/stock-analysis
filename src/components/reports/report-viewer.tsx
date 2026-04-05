"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

export function ReportViewer({ markdown }: { markdown: string }) {
  if (!markdown) {
    return (
      <div className="py-12 text-center text-sm text-zinc-400">
        보고서가 생성되지 않았습니다.
      </div>
    )
  }

  return (
    <div className="report-viewer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-4 mt-8 text-2xl font-bold text-zinc-900 first:mt-0 dark:text-zinc-100">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-3 mt-6 text-xl font-semibold text-zinc-800 dark:text-zinc-200">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 mt-4 text-lg font-semibold text-zinc-700 dark:text-zinc-300">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="mb-3 leading-relaxed text-zinc-700 dark:text-zinc-400">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="mb-3 ml-6 list-disc space-y-1 text-zinc-700 dark:text-zinc-400">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-3 ml-6 list-decimal space-y-1 text-zinc-700 dark:text-zinc-400">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-3 border-l-4 border-zinc-300 bg-zinc-50 py-2 pl-4 italic text-zinc-600 dark:border-zinc-600 dark:bg-zinc-800/50 dark:text-zinc-400">
              {children}
            </blockquote>
          ),
          code: ({ children, className }) => {
            const isBlock = className?.includes("language-")
            if (isBlock) {
              return (
                <code className="block overflow-x-auto rounded-md bg-zinc-900 p-4 text-sm text-zinc-100">
                  {children}
                </code>
              )
            }
            return (
              <code className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-sm text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
                {children}
              </code>
            )
          },
          pre: ({ children }) => <pre className="mb-3">{children}</pre>,
          table: ({ children }) => (
            <div className="mb-3 overflow-x-auto">
              <table className="w-full border-collapse border border-zinc-300 text-sm dark:border-zinc-600">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-zinc-100 dark:bg-zinc-800">{children}</thead>
          ),
          th: ({ children }) => (
            <th className="border border-zinc-300 px-3 py-2 text-left font-semibold text-zinc-700 dark:border-zinc-600 dark:text-zinc-300">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-zinc-300 px-3 py-2 text-zinc-600 dark:border-zinc-600 dark:text-zinc-400">
              {children}
            </td>
          ),
          hr: () => <hr className="my-6 border-zinc-200 dark:border-zinc-700" />,
          strong: ({ children }) => (
            <strong className="font-semibold text-zinc-900 dark:text-zinc-100">
              {children}
            </strong>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              className="text-blue-600 underline hover:text-blue-800 dark:text-blue-400"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  )
}
