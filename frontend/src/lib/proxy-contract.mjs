const FORWARDED_REQUEST_HEADERS = [
  'accept',
  'content-type',
  'cookie',
  'if-none-match',
  'if-modified-since',
  'x-forwarded-for',
  'x-forwarded-proto',
];

const FORWARDED_RESPONSE_HEADERS = [
  'cache-control',
  'content-disposition',
  'content-type',
  'etag',
  'last-modified',
  'retry-after',
];

export async function resolveProxyPath(params) {
  const resolved = await params;
  const segments = resolved?.proxy ?? [];
  if (!Array.isArray(segments)) throw new TypeError('Invalid proxy path');
  return segments
    .map((segment) => {
      if (
        typeof segment !== 'string' ||
        !segment ||
        segment === '.' ||
        segment === '..' ||
        segment.includes('/') ||
        segment.includes('\\')
      ) {
        throw new TypeError('Invalid proxy path');
      }
      return encodeURIComponent(segment);
    })
    .join('/');
}

export function buildUpstreamUrl(backend, path, search = '') {
  const base = backend.replace(/\/+$/, '');
  const query = !search ? '' : search.startsWith('?') ? search : `?${search}`;
  return `${base}/api/${path}${query}`;
}

export function buildUpstreamHeaders(source) {
  const headers = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = source.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}

export function buildResponseHeaders(source) {
  const headers = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = source.get(name);
    if (value) headers.set(name, value);
  }

  const getSetCookie = source.getSetCookie;
  if (typeof getSetCookie === 'function') {
    for (const value of getSetCookie.call(source)) {
      headers.append('set-cookie', value);
    }
  } else {
    const value = source.get('set-cookie');
    if (value) headers.append('set-cookie', value);
  }
  return headers;
}
