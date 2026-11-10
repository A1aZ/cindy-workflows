#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const files = [];
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === '.git') continue; // Worktrees use a .git file pointing outside the package.
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!['.git', 'assets'].includes(entry.name)) walk(file);
    } else if (!/node_modules|__pycache__|\.pyc$/.test(file)) files.push(file);
  }
}
walk(root);

const forbidden = [
  /\/Users\//,
  /[A-Za-z]:\\Users\\/,
  /Bearer\s+[A-Za-z0-9._-]{20,}/i,
  /(?:access[_-]?token|refresh[_-]?token|client[_-]?secret|password)\s*[:=]/i,
  /oc_[a-z0-9]{20,}/i,
  /github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/issues\/\d+/i,
  /[A-Za-z0-9._%+-]+@(?!(?:[A-Za-z0-9-]+\.)*example\.(?:com|invalid|org)\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}/i,
];
const violations = [];
for (const file of files) {
  const text = fs.readFileSync(file, 'utf8');
  for (const pattern of forbidden) {
    if (pattern.test(text)) violations.push(`${path.relative(root, file)}: ${pattern}`);
  }
}
if (violations.length) {
  console.error('REDACTION CHECK FAILED');
  for (const item of violations) console.error(item);
  process.exit(1);
}
console.log(`REDACTION CHECK PASSED (${files.length} text files; binary assets excluded)`);
