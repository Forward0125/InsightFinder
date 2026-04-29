'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Search, Workflow, LayoutDashboard } from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItem {
  href:  string
  label: string
  icon:  React.ComponentType<{ size?: number; className?: string }>
}

const NAV_ITEMS: NavItem[] = [
  { href: '/',           label: 'Query',      icon: Search          },
  { href: '/pipelines',  label: 'Pipelines',  icon: Workflow        },
  { href: '/dashboard',  label: 'Dashboard',  icon: LayoutDashboard },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside
      className={cn(
        'fixed inset-y-0 left-0 z-30 w-60 flex flex-col',
        'bg-surface/40 backdrop-blur-md',
        'border-r border-border/8',
      )}
      aria-label="Primary"
    >
      {/* Brand */}
      <div className="h-16 flex items-center gap-2.5 px-5 border-b border-border/6">
        <div className="grid place-items-center h-7 w-7 rounded-md bg-gradient-accent">
          <Search size={14} className="text-background" />
        </div>
        <span className="font-display font-bold text-base tracking-tight leading-none">
          InsightFinder
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-5 space-y-0.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active =
            href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium',
                'transition-colors duration-150',
                active
                  ? 'bg-surface-high text-foreground'
                  : 'text-foreground-2 hover:text-foreground hover:bg-surface-high/50',
              )}
            >
              <Icon size={16} className={active ? 'text-accent-warm' : ''} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border/6">
        <p className="text-[10px] font-mono text-foreground-3 tracking-[0.15em] uppercase">
          v0.1.0 · dev
        </p>
      </div>
    </aside>
  )
}
