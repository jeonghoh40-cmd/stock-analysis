import { NextRequest } from "next/server"
import path from "path"
import fs from "fs/promises"

const UPLOAD_ROOT = process.env.UPLOAD_ROOT || path.join(process.cwd(), "uploads")

// 허용 확장자 화이트리스트
const ALLOWED_EXTENSIONS = new Set([
  ".pdf", ".pptx", ".ppt", ".xlsx", ".xls",
  ".docx", ".doc", ".hwp", ".hwpx", ".txt", ".md",
])

// 안전한 기업명 검증
const SAFE_NAME_RE = /^[\w\s\uAC00-\uD7A3._-]+$/

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const company = formData.get("company") as string

  if (!company) {
    return Response.json({ error: "company는 필수입니다." }, { status: 400 })
  }

  if (!SAFE_NAME_RE.test(company)) {
    return Response.json({ error: "기업명에 허용되지 않는 문자가 포함되어 있습니다." }, { status: 400 })
  }

  const uploadDir = path.join(UPLOAD_ROOT, company)

  // 기존 업로드 파일 정리 후 새로 생성
  try {
    await fs.rm(uploadDir, { recursive: true, force: true })
  } catch {
    // 디렉토리가 없으면 무시
  }
  await fs.mkdir(uploadDir, { recursive: true })

  const files = formData.getAll("files") as File[]
  if (files.length === 0) {
    return Response.json({ error: "파일이 없습니다." }, { status: 400 })
  }

  const saved: string[] = []
  const rejected: string[] = []
  for (const file of files) {
    const ext = path.extname(file.name).toLowerCase()
    if (!ALLOWED_EXTENSIONS.has(ext)) {
      rejected.push(file.name)
      continue
    }
    // 파일명에서 경로 탐색 문자 제거
    const safeName = path.basename(file.name)
    const buffer = Buffer.from(await file.arrayBuffer())
    const filePath = path.join(uploadDir, safeName)
    await fs.writeFile(filePath, buffer)
    saved.push(safeName)
  }

  if (saved.length === 0) {
    return Response.json(
      { error: `지원하지 않는 파일 형식입니다: ${rejected.join(", ")}` },
      { status: 400 }
    )
  }

  return Response.json({
    uploadDir,
    files: saved,
    rejected: rejected.length > 0 ? rejected : undefined,
    message: `${saved.length}개 파일 업로드 완료${rejected.length > 0 ? ` (${rejected.length}개 거부됨)` : ""}`,
  })
}
