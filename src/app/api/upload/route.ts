import { NextRequest } from "next/server"
import path from "path"
import fs from "fs/promises"

const UPLOAD_ROOT = process.env.UPLOAD_ROOT || path.join(process.cwd(), "uploads")

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const company = formData.get("company") as string

  if (!company) {
    return Response.json({ error: "company는 필수입니다." }, { status: 400 })
  }

  const uploadDir = path.join(UPLOAD_ROOT, company)
  await fs.mkdir(uploadDir, { recursive: true })

  const files = formData.getAll("files") as File[]
  if (files.length === 0) {
    return Response.json({ error: "파일이 없습니다." }, { status: 400 })
  }

  const saved: string[] = []
  for (const file of files) {
    const buffer = Buffer.from(await file.arrayBuffer())
    const filePath = path.join(uploadDir, file.name)
    await fs.writeFile(filePath, buffer)
    saved.push(file.name)
  }

  return Response.json({
    uploadDir,
    files: saved,
    message: `${saved.length}개 파일 업로드 완료`,
  })
}
