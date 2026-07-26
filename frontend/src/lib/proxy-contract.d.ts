export function resolveProxyPath(
  params:
    | Promise<{ proxy?: string[] }>
    | { proxy?: string[] },
): Promise<string>;

export function buildUpstreamUrl(
  backend: string,
  path: string,
  search?: string,
): string;

export function buildUpstreamHeaders(source: Headers): Headers;
export function buildResponseHeaders(source: Headers): Headers;
