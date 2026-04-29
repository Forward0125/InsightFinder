'use client'

import { ThemeProvider as NextThemesProvider } from 'next-themes'
import type { ThemeProviderProps } from 'next-themes'

/**
 * Wraps next-themes with InsightFinder defaults.
 * - defaultTheme: "dark" — dark mode is the primary experience
 * - attribute: "class" — adds "dark" or "light" to <html>
 * - enableSystem: false — explicit choice, ignores OS preference
 */
export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      disableTransitionOnChange={false}
      value={{ dark: 'dark', light: 'light' }}
      {...props}
    >
      {children}
    </NextThemesProvider>
  )
}
