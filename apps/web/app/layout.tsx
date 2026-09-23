import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Mappet',
  description: 'Find nearby running/walking loops shaped like recognisable objects.',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#2563eb',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="h-full bg-slate-100 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  )
}
