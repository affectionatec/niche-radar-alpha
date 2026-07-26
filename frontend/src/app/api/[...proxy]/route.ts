import { NextRequest, NextResponse } from 'next/server';
import {
  buildUpstreamUrl,
  buildResponseHeaders,
  buildUpstreamHeaders,
  resolveProxyPath,
} from '@/lib/proxy-contract.mjs';

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8000';

type RouteContext = {
  params: Promise<{ proxy?: string[] }>;
};

async function handle(
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  let path: string;
  try {
    path = await resolveProxyPath(context.params);
  } catch {
    return NextResponse.json({ error: 'Invalid proxy path' }, { status: 400 });
  }
  const target = buildUpstreamUrl(BACKEND, path, request.nextUrl.search);
  const body =
    request.method === 'GET' || request.method === 'HEAD'
      ? undefined
      : await request.arrayBuffer();

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers: buildUpstreamHeaders(request.headers),
      body,
      cache: 'no-store',
      redirect: 'manual',
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: `Backend unreachable: ${message}` },
      { status: 502 },
    );
  }

  return new NextResponse(await upstream.arrayBuffer(), {
    status: upstream.status,
    headers: buildResponseHeaders(upstream.headers),
  });
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const DELETE = handle;
