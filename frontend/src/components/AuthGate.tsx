'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { AUTH_REQUIRED_EVENT, getSession } from '@/lib/client';

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(pathname === '/login');

  useEffect(() => {
    if (pathname === '/login') {
      setReady(true);
      return;
    }

    let active = true;
    setReady(false);
    getSession()
      .then(() => {
        if (active) setReady(true);
      })
      .catch(() => {
        if (!active) return;
        const next = `${window.location.pathname}${window.location.search}`;
        router.replace(`/login?next=${encodeURIComponent(next)}`);
      });

    const unauthorized = () => router.replace('/login');
    window.addEventListener(AUTH_REQUIRED_EVENT, unauthorized);
    return () => {
      active = false;
      window.removeEventListener(AUTH_REQUIRED_EVENT, unauthorized);
    };
  }, [pathname, router]);

  if (!ready) {
    return (
      <div className="radar-auth-loading" role="status" aria-live="polite">
        <span>[ SCANNING SESSION ]</span>
      </div>
    );
  }
  return <>{children}</>;
}
