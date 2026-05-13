import type { Metadata } from 'next';
import { GeistMono } from 'geist/font/mono';
import { Inter } from 'next/font/google';
import './globals.css';
import Navigation from '@/components/Navigation';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'Niche Radar',
  description: 'Automated trend-intelligence pipeline',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${GeistMono.variable} ${inter.variable}`}>
      <body style={{ backgroundColor: '#1f2228' }}>
        <Navigation />
        <main
          style={{
            maxWidth: '1200px',
            margin: '0 auto',
            padding: '48px 24px',
          }}
        >
          {children}
        </main>
      </body>
    </html>
  );
}
