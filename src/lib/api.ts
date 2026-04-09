import type {
  CompanyCodes,
  FullAnalysisResponse,
  MonitoringAlert,
  PortfolioCompany,
  SimilarResponse,
  UploadExtractResponse,
} from "./types"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
const API_KEY = process.env.NEXT_PUBLIC_VC_API_KEY || ""

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" }
  if (API_KEY) h["X-API-Key"] = API_KEY
  return h
}

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const errorBody = await res.json()
      detail = errorBody?.detail || errorBody?.error || detail
    } catch {
      // body가 JSON이 아니면 statusText 그대로 사용
    }
    throw new Error(`API error: ${res.status} ${detail}`)
  }
  return res.json()
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: headers(),
    signal,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const errorBody = await res.json()
      detail = errorBody?.detail || errorBody?.error || detail
    } catch {
      // body가 JSON이 아니면 statusText 그대로 사용
    }
    throw new Error(`API error: ${res.status} ${detail}`)
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// Analysis
// ---------------------------------------------------------------------------

export async function analyzeCompany(
  codes: CompanyCodes,
  signal?: AbortSignal
): Promise<FullAnalysisResponse> {
  return post("/api/v1/analysis/full", codes, signal)
}

export async function searchSimilarCases(
  codes: CompanyCodes,
  signal?: AbortSignal
): Promise<SimilarResponse> {
  return post("/api/v1/analysis/similar", codes, signal)
}

// ---------------------------------------------------------------------------
// File Upload
// ---------------------------------------------------------------------------

export function uploadAndExtract(
  files: File[],
  onProgress?: (percent: number) => void,
  signal?: AbortSignal
): Promise<UploadExtractResponse> {
  return new Promise((resolve, reject) => {
    const formData = new FormData()
    files.forEach((f) => formData.append("files", f))

    const xhr = new XMLHttpRequest()
    xhr.open("POST", `${API_BASE}/api/v1/upload/extract`)

    if (API_KEY) {
      xhr.setRequestHeader("X-API-Key", API_KEY)
    }

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`))
      }
    }

    xhr.onerror = () => reject(new Error("Upload failed: network error"))
    xhr.onabort = () => reject(new DOMException("Upload aborted", "AbortError"))

    if (signal) {
      if (signal.aborted) {
        xhr.abort()
        reject(new DOMException("Upload aborted", "AbortError"))
        return
      }
      signal.addEventListener("abort", () => xhr.abort(), { once: true })
    }

    xhr.send(formData)
  })
}

// ---------------------------------------------------------------------------
// Monitoring
// ---------------------------------------------------------------------------

export async function getPortfolio(signal?: AbortSignal): Promise<PortfolioCompany[]> {
  return get("/api/v1/monitoring/portfolio", signal)
}

export async function getAlerts(signal?: AbortSignal): Promise<MonitoringAlert[]> {
  return get("/api/v1/monitoring/alerts", signal)
}

export async function getCompanyDetail(company: string, signal?: AbortSignal): Promise<unknown> {
  return get(`/api/v1/monitoring/${encodeURIComponent(company)}/detail`, signal)
}

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

export async function healthCheck(): Promise<boolean> {
  try {
    await get("/")
    return true
  } catch {
    return false
  }
}
