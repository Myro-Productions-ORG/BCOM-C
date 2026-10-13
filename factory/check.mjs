#!/usr/bin/env node
// Repo "test command": syntax-checks JS, inline <script> blocks, and daemon Python. No deps.
// Usage: node factory/check.mjs [repoRoot]
import { readdirSync, readFileSync, writeFileSync, mkdtempSync, existsSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(process.argv[2] ?? join(dirname(fileURLToPath(import.meta.url)), '..'));
const tmp = mkdtempSync(join(tmpdir(), 'bcom-check-'));
let checked = 0, failed = 0;

const list = (dir, ext) => existsSync(join(root, dir))
  ? readdirSync(join(root, dir)).filter(f => f.endsWith(ext)).sort().map(f => `${dir}/${f}`) : [];

function report(label, err) {
  checked++;
  if (err) { failed++; console.log(`FAIL ${label}: ${err}`); } else console.log(`ok  ${label}`);
}

// Returns first error line from `node --check`, or null. lineOffset maps temp-file lines to html lines.
function nodeCheck(file, lineOffset = 0) {
  const r = spawnSync(process.execPath, ['--check', file], { encoding: 'utf8' });
  if (r.status === 0) return null;
  const lines = r.stderr.split('\n');
  const m = lines[0].match(/:(\d+)$/);
  const msg = lines.find(l => /Error/.test(l)) ?? lines[0];
  return m ? `line ${Number(m[1]) + lineOffset}: ${msg}` : msg;
}

for (const f of list('assets/js', '.js')) report(f, nodeCheck(join(root, f)));

const JS_TYPES = new Set(['', 'text/javascript', 'application/javascript', 'module']);
const scriptRe = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
for (const f of ['index.html', ...list('pages', '.html')]) {
  if (!existsSync(join(root, f))) continue;
  const html = readFileSync(join(root, f), 'utf8');
  const fails = [];
  let n = 0, total = 0, m;
  while ((m = scriptRe.exec(html))) {
    const [, attrs, body] = m;
    if (/\bsrc\s*=/i.test(attrs)) continue;
    const type = (attrs.match(/\btype\s*=\s*["']?([^"'\s>]+)/i)?.[1] ?? '').toLowerCase();
    if (!JS_TYPES.has(type)) continue;
    n++;
    const bodyStart = m.index + m[0].indexOf('>') + 1;
    const startLine = html.slice(0, bodyStart).split('\n').length; // html line where body begins
    const tf = join(tmp, `s${n}${type === 'module' ? '.mjs' : '.js'}`);
    writeFileSync(tf, body);
    const err = nodeCheck(tf, startLine - 1);
    if (err) fails.push(`${f} (script #${n}, ${err.replace(/^line (\d+): /, 'line $1): ')}`);
    total++;
  }
  if (fails.length) { checked++; failed++; fails.forEach(x => console.log(`FAIL ${x}`)); }
  else report(`${f} (${total} inline script${total === 1 ? '' : 's'})`, null);
}

const env = { ...process.env, PYTHONPYCACHEPREFIX: join(tmp, 'pycache') };
for (const f of list('daemon', '.py')) {
  const r = spawnSync('python3', ['-m', 'py_compile', join(root, f)], { encoding: 'utf8', env });
  report(f, r.status === 0 ? null : (r.stderr.trim().split('\n').pop() || 'py_compile failed'));
}

console.log(`${checked} checked, ${failed} failed`);
process.exit(failed ? 1 : 0);
