#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const root = path.resolve(import.meta.dirname, '..');
const required = [
  'README.md',
  'install.mjs',
  'skills/sausage-man-monitor/SKILL.md',
  'skills/sausage-man-monitor/PACKAGE.json',
  'skills/sausage-man-monitor/scripts/query.py',
  'skills/sausage-man-monitor/scripts/package_skill.py',
  'skills/filo-support-replies/SKILL.md',
  'skills/filo-support-replies/assets/support-policy.example.json',
  'skills/filo-support-replies/scripts/validate_policy.py',
  'skills/filoai-feedback-triage/SKILL.md',
  'skills/filoai-feedback-triage/assets/config.example.json',
  'skills/filoai-feedback-triage/scripts/validate-config.mjs',
  'skills/cindy-update-poster/SKILL.md',
  'skills/model-comparison-poster/SKILL.md',
  'skills/xiaohongshu-feedback-monitor/SKILL.md',
  'workflows/cindy-update-poster/README.md',
  'workflows/cindy-update-poster/collect.py',
  'workflows/cindy-update-poster/poster.py',
  'workflows/cindy-update-poster/html_poster.py',
  'workflows/cindy-update-poster/capture_poster.py',
  'workflows/cindy-update-poster/pose_library.py',
  'workflows/cindy-update-poster/assets/pose-library.json',
  'workflows/cindy-update-poster/assets/brand/std-white.png',
  'workflows/cindy-update-poster/assets/brand/BebasNeue-Regular.ttf',
  'templates/config/cindy-update-poster.example.json',
  'templates/config/model-comparison-poster.example.json',
  'templates/schedules/cindy-update-poster.txt',
  'templates/schedules/model-comparison-poster.txt',
  'workflows/model-comparison-poster/README.md',
  'workflows/model-comparison-poster/scripts/validate_facts.py',
  'workflows/model-comparison-poster/scripts/render.py',
  'workflows/model-comparison-poster/scripts/capture_poster.py',
  'templates/config/support-policy.example.json',
  'templates/config/feedback-triage.example.json',
  'templates/config/xiaohongshu-feedback.example.json',
  'templates/schedules/support-replies.txt',
  'templates/schedules/feedback-triage.txt',
  'templates/schedules/xiaohongshu-feedback-monitor.txt',
  'templates/schedules/xiaohongshu-feedback-monitor.yaml',
];
const missing = required.filter(file => !fs.existsSync(path.join(root, file)));
if (missing.length) {
  console.error('PACKAGE CHECK FAILED');
  missing.forEach(file => console.error(`missing: ${file}`));
  process.exit(1);
}
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'workflows/cindy-update-poster/assets/pose-library.json'), 'utf8'));
const enabled = manifest.assets.filter(item => item.enabled !== false);
for (const item of enabled) {
  const file = `workflows/cindy-update-poster/assets/poses/${item.name}.png`;
  if (!fs.existsSync(path.join(root, file))) {
    console.error(`PACKAGE CHECK FAILED: missing enabled pose ${file}`);
    process.exit(1);
  }
}
const chromeSource = fs.readFileSync(path.join(root, 'workflows/cindy-update-poster/capture_poster.py'), 'utf8');
if (!chromeSource.includes('WIDTH = 1240')
  || !chromeSource.includes('full_page=True')
  || !chromeSource.includes('set_viewport_size')
  || !chromeSource.includes('headless=True')) {
  console.error('PACKAGE CHECK FAILED: Chrome capture contract missing');
  process.exit(1);
}
const htmlSource = fs.readFileSync(path.join(root, 'workflows/cindy-update-poster/html_poster.py'), 'utf8');
if (!htmlSource.includes('WORDMARK_SHA256')
  || !htmlSource.includes('BACKGROUND_PACK')
  || !htmlSource.includes('secrets.choice')
  || !htmlSource.includes('object-position:center top')
  || !htmlSource.includes('height:auto')) {
  console.error('PACKAGE CHECK FAILED: brand/veil contract missing');
  process.exit(1);
}
const wordmark = fs.readFileSync(path.join(root, 'workflows/cindy-update-poster/assets/brand/std-white.png'));
const hash = crypto.createHash('sha256').update(wordmark).digest('hex');
if (hash !== '7ae927c07f7334e337e8f7c9217f8133a8d009032b2f653616528173e4cc9e4b') {
  console.error(`PACKAGE CHECK FAILED: wordmark checksum ${hash}`);
  process.exit(1);
}
console.log(`PACKAGE CHECK PASSED (${required.length} required files, ${enabled.length} enabled poses)`);
console.log('WORDMARK CHECK PASSED');
