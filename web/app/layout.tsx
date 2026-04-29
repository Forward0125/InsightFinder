import type { Metadata, Viewport } from 'next'
import { Inter, Space_Grotesk, JetBrains_Mono } from 'next/font/google'
import { ThemeProvider } from '@/providers/ThemeProvider'
import { Sidebar } from '@/components/layout/Sidebar'
import './globals.css'

/* ─── Fonts ──────────────────────────────────────────────────── */

const inter = Inter({
  subsets:  ['latin'],
  variable: '--font-inter',
  display:  'swap',
})

const spaceGrotesk = Space_Grotesk({
  subsets:  ['latin'],
  variable: '--font-space-grotesk',
  display:  'swap',
  weight:   ['400', '500', '600', '700'],
})

const jetbrainsMono = JetBrains_Mono({
  subsets:  ['latin'],
  variable: '--font-jetbrains-mono',
  display:  'swap',
  weight:   ['400', '500'],
})

/* ─── Metadata ───────────────────────────────────────────────── */

export const metadata: Metadata = {
  title: {
    default:  'InsightFinder',
    template: '%s · InsightFinder',
  },
  description:
    'Production RAG search over SEC filings — hybrid retrieval, cited answers, and live evaluation gates.',
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: dark)',  color: '#04040C' },
    { media: '(prefers-color-scheme: light)', color: '#F8F6F2' },
  ],
  width:        'device-width',
  initialScale: 1,
}

/* ─── Root Layout ────────────────────────────────────────────── */

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={[
        inter.variable,
        spaceGrotesk.variable,
        jetbrainsMono.variable,
      ].join(' ')}
    >
      <body className="min-h-dvh antialiased">
        <ThemeProvider>
          <Sidebar />

          <main
            id="main-content"
            className="ml-60 min-h-dvh flex flex-col"
          >
            {children}
          </main>
        </ThemeProvider>
      </body>
    </html>
  )
}
