import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
  buildUpstreamUrl,
  buildResponseHeaders,
  buildUpstreamHeaders,
  resolveProxyPath,
} from '../src/lib/proxy-contract.mjs';

test('resolves and encodes a promised catch-all path', async () => {
  assert.equal(
    await resolveProxyPath(Promise.resolve({ proxy: ['reports', '中文 item'] })),
    'reports/%E4%B8%AD%E6%96%87%20item',
  );
});

test('rejects path traversal and slash injection', async () => {
  await assert.rejects(() => resolveProxyPath({ proxy: ['..'] }), /Invalid/);
  await assert.rejects(() => resolveProxyPath({ proxy: ['a/b'] }), /Invalid/);
  await assert.rejects(() => resolveProxyPath({ proxy: ['a\\b'] }), /Invalid/);
});

test('preserves an encoded path and the complete query string', () => {
  assert.equal(
    buildUpstreamUrl(
      'http://radar:8000/',
      'reports/%E4%B8%AD%E6%96%87%20item',
      '?format=csv&tag=a%2Fb',
    ),
    'http://radar:8000/api/reports/%E4%B8%AD%E6%96%87%20item?format=csv&tag=a%2Fb',
  );
});

test('route exports every supported mutation and read method', () => {
  const route = readFileSync(
    new URL('../src/app/api/[...proxy]/route.ts', import.meta.url),
    'utf8',
  );
  for (const method of ['GET', 'POST', 'PUT', 'DELETE']) {
    assert.match(route, new RegExp(`export const ${method}\\s*=\\s*handle`));
  }
});

test('forwards Cookie and content negotiation but not Host', () => {
  const source = new Headers({
    accept: 'application/json',
    cookie: 'session=secret',
    host: 'radar.originbase.org',
    connection: 'keep-alive',
    'x-forwarded-for': '203.0.113.30',
    'x-forwarded-proto': 'https',
  });
  const result = buildUpstreamHeaders(source);
  assert.equal(result.get('accept'), 'application/json');
  assert.equal(result.get('cookie'), 'session=secret');
  assert.equal(result.get('x-forwarded-for'), '203.0.113.30');
  assert.equal(result.get('x-forwarded-proto'), 'https');
  assert.equal(result.get('host'), null);
  assert.equal(result.get('connection'), null);
});

test('forwards response metadata and Set-Cookie only', () => {
  const source = new Headers({
    'content-type': 'application/json',
    'set-cookie': 'session=value; HttpOnly; Secure',
    connection: 'close',
  });
  const result = buildResponseHeaders(source);
  assert.equal(result.get('content-type'), 'application/json');
  assert.match(result.get('set-cookie') ?? '', /HttpOnly/);
  assert.equal(result.get('connection'), null);
});
