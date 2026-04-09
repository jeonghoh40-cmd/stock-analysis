"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Home,
  Play,
  Plus,
  History,
  Search,
  Briefcase,
  TrendingUp,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"

type NavItem = { href: string; label: string; icon: LucideIcon }

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "홈", icon: Home },
  { href: "/run", label: "분석 실행", icon: Play },
  { href: "/analysis/new", label: "새 분석", icon: Plus },
  { href: "/history", label: "분석 이력", icon: History },
  { href: "/similar", label: "유사 케이스", icon: Search },
  { href: "/monitoring", label: "포트폴리오", icon: Briefcase },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="flex w-64 shrink-0 flex-col bg-zinc-900 text-zinc-100">
      <div className="flex h-16 items-center gap-2 border-b border-zinc-800 px-6">
        <TrendingUp className="h-6 w-6 text-blue-400" strokeWidth={2} />
        <span className="text-lg font-bold tracking-tight">VC 투자 분석</span>
      </div>

      <nav className="flex flex-col gap-1 p-4">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href)

          const Icon = item.icon

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-zinc-800 text-white"
                  : "text-zinc-400 hover:bg-zinc-800 hover:text-white"
              )}
            >
              <Icon className="h-5 w-5 shrink-0" strokeWidth={1.5} />
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="mt-auto border-t border-zinc-800 p-4">
        <div className="text-xs text-zinc-500">VC Investment Analyzer v2.0</div>
      </div>
    </aside>
  )
}
