import { NextRequest } from "next/server"
import fs from "fs/promises"
import path from "path"
import os from "os"

type EntryInfo = {
  name: string
  path: string
  isDir: boolean
  size: number
  modified: string
}

// 탐색 가능한 루트 경로 목록 (Windows/Linux 대응)
async function getRoots(): Promise<EntryInfo[]> {
  const roots: EntryInfo[] = []

  if (process.platform === "win32") {
    // Windows: 드라이브 문자 탐색
    for (const letter of "CDEFGHIJKLMNOPQRSTUVWXYZ") {
      const drive = `${letter}:\\`
      try {
        await fs.access(drive)
        roots.push({
          name: `${letter}: 드라이브`,
          path: drive,
          isDir: true,
          size: 0,
          modified: "",
        })
      } catch {
        // 존재하지 않는 드라이브
      }
    }
  } else {
    // Linux/Mac
    roots.push({ name: "/", path: "/", isDir: true, size: 0, modified: "" })

    // Docker 마운트 경로
    for (const dir of ["/data", "/mnt"]) {
      try {
        await fs.access(dir)
        roots.push({ name: dir, path: dir, isDir: true, size: 0, modified: "" })
      } catch {
        // skip
      }
    }
  }

  // 홈 디렉토리
  const home = os.homedir()
  roots.push({ name: "홈 폴더", path: home, isDir: true, size: 0, modified: "" })

  return roots
}

export async function POST(request: NextRequest) {
  const { dirPath } = await request.json()

  // dirPath가 없으면 루트 목록 반환
  if (!dirPath) {
    const roots = await getRoots()
    return Response.json({ entries: roots, currentPath: "", parentPath: null })
  }

  try {
    const resolvedPath = path.resolve(dirPath)
    const entries: EntryInfo[] = []
    const dirEntries = await fs.readdir(resolvedPath, { withFileTypes: true })

    for (const entry of dirEntries) {
      // 숨김 파일/시스템 폴더 제외
      if (entry.name.startsWith(".") || entry.name.startsWith("$")) continue
      if (["node_modules", "__pycache__", ".git"].includes(entry.name)) continue

      const fullPath = path.join(resolvedPath, entry.name)
      try {
        const stat = await fs.stat(fullPath)
        entries.push({
          name: entry.name,
          path: fullPath,
          isDir: stat.isDirectory(),
          size: stat.size,
          modified: stat.mtime.toISOString(),
        })
      } catch {
        // 접근 불가한 파일 건너뛰기
      }
    }

    // 폴더 먼저, 이름순 정렬
    entries.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1
      return a.name.localeCompare(b.name)
    })

    const parentPath = path.dirname(resolvedPath)

    return Response.json({
      entries,
      currentPath: resolvedPath,
      parentPath: parentPath !== resolvedPath ? parentPath : null,
    })
  } catch (err: unknown) {
    const e = err as NodeJS.ErrnoException
    let message = `경로를 열 수 없습니다: ${dirPath}`
    if (e.code === "ENOENT") {
      message = `경로가 존재하지 않습니다: ${dirPath}`
    } else if (e.code === "EACCES" || e.code === "EPERM") {
      message = `접근 권한이 없습니다: ${dirPath}`
    } else if (e.code === "ENOTDIR") {
      message = `폴더가 아닙니다: ${dirPath}`
    } else if (e.message?.includes("network")) {
      message = `네트워크 경로에 접근할 수 없습니다. 드라이브가 연결되어 있는지 확인하세요: ${dirPath}`
    }
    return Response.json(
      { error: message, entries: [], currentPath: dirPath, parentPath: null },
      { status: 400 }
    )
  }
}
