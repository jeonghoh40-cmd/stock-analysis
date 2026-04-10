import { NextRequest } from "next/server"
import { marked } from "marked"
import htmlToDocx from "html-to-docx"

export const runtime = "nodejs"

// 안전한 파일명 검증
const SAFE_NAME_RE = /^[\w\s\uAC00-\uD7A3._-]+$/

export async function POST(request: NextRequest) {
  const { markdown, filename } = await request.json()

  if (typeof markdown !== "string" || !markdown.trim()) {
    return Response.json({ error: "markdown은 필수입니다." }, { status: 400 })
  }

  if (typeof filename !== "string" || !SAFE_NAME_RE.test(filename)) {
    return Response.json({ error: "잘못된 파일명입니다." }, { status: 400 })
  }

  // 마크다운 → HTML
  const bodyHtml = await marked.parse(markdown, { async: true })
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>${bodyHtml}</body></html>`

  // HTML → DOCX
  const result = await htmlToDocx(html, null, {
    table: { row: { cantSplit: true } },
    footer: false,
    pageNumber: false,
  })

  // html-to-docx는 Node 환경에서 Buffer를 반환
  const buffer = result instanceof Buffer ? result : Buffer.from(await (result as Blob).arrayBuffer())

  return new Response(new Uint8Array(buffer), {
    headers: {
      "Content-Type":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(filename)}.docx`,
    },
  })
}
