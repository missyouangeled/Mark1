import type { Metadata } from 'next';
import './globals.css';
import { SiteHeader } from '@/components/site-header';
import { SiteFooter } from '@/components/site-footer';
import { FloatingDock } from '@/components/floating-dock';

export const metadata: Metadata = {
  title: 'PulseNest Prototype',
  description: 'A TapTap-inspired original front-end prototype built with Next.js and Tailwind CSS.'
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <SiteHeader />
        <main>{children}</main>
        <SiteFooter />
        <FloatingDock />
      </body>
    </html>
  );
}
