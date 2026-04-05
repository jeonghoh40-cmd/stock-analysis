import { NextRequest } from "next/server"
import fs from "fs/promises"
import path from "path"

export async function GET(request: NextRequest) {
  const filePath = request.nextUrl.searchParams.get("path")

  if (!filePath) {
    return Response.json({ error: "path 파라미터가 필요합니다." }, { status: 400 })
  }

  try {
    const buffer = await fs.readFile(filePath)
    const fileName = path.basename(filePath)

    return new Response(buffer, {
      headers: {
        "Content-Type":
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(fileName)}`,
      },
    })
  } catch {
    return Response.json({ error: "파일을 찾을 수 없습니다." }, { status: 404 })
  }
}

export async function POST(request: NextRequest) {
  const { directory } = await request.json()

  if (!directory) {
    return Response.json({ error: "directory가 필요합니다." }, { status: 400 })
  }

  try {
    const entries = await fs.readdir(directory)
    const docxFiles = entries.filter(
      (f) => f.endsWith(".docx") && !f.startsWith("~")
    )
    const files = await Promise.all(
      docxFiles.map(async (name) => {
        const fullPath = path.join(directory, name)
        const stat = await fs.stat(fullPath)
        return { name, path: fullPath, size: stat.size, modified: stat.mtime }
      })
    )
    files.sort((a, b) => new Date(b.modified).getTime() - new Date(a.modified).getTime())
    return Response.json({ files })
  } catch {
    return Response.json({ files: [] })
  }
}
