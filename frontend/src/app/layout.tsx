import type { Metadata } from 'next';
import { GeistMono } from 'geist/font/mono';
import { Inter } from 'next/font/google';
import './globals.css';
import Navigation from '@/components/Navigation';
import AuthGate from '@/components/AuthGate';

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
        <a href="#main-content" className="skip-to-content">Skip to content</a>
        <AuthGate>
          <Navigation />
          <main
            id="main-content"
            style={{
              maxWidth: '1200px',
              margin: '0 auto',
              padding: '48px 24px',
            }}
          >
            {children}
          </main>
        </AuthGate>
      </body>
    </html>
  );
}
