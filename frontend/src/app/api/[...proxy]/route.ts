import { NextRequest, NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:8000';

async function handle(
  request: NextRequest,
  { params }: { params: { proxy: string[] } },
): Promise<NextResponse> {
  const path = (params.proxy ?? []).join('/');
  const search = request.nextUrl.search;
  const target = `${BACKEND}/api/${path}${search}`;

  const headers: Record<string, string> = {};
  const ct = request.headers.get('content-type');
  if (ct) headers['content-type'] = ct;

  let body: ArrayBuffer | undefined;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    body = await request.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, { method: request.method, headers, body });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: `Backend unreachable: ${msg}` }, { status: 502 });
  }

  const responseBody = await upstream.arrayBuffer();
  const responseHeaders = new Headers();
  const upstreamCt = upstream.headers.get('content-type');
  if (upstreamCt) responseHeaders.set('content-type', upstreamCt);

  return new NextResponse(responseBody, { status: upstream.status, headers: responseHeaders });
}

export const GET = handle;
export const POST = handle;
