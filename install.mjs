#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { execFileSync } from 'node:child_process';
import readline from 'node:readline/promises';

const packageRoot = path.resolve(import.meta.dirname);
const args = process.argv.slice(2);
function argValue(name) {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : undefined;
}
const workflowArg = argValue('--workflow') || 'all';
const targetArg = argValue('--target');
const target = path.resolve(targetArg || process.cwd());
const interactive = args.includes('--interactive') && !args.includes('--non-interactive');
const rl = interactive ? readline.createInterface({ input: process.stdin, output: process.stdout }) : null;

const workflowAliases = {
  all: ['filo-support-replies', 'filoai-feedback-triage', 'cindy-update-poster', 'model-comparison-poster', 'xiaohongshu-feedback-monitor', 'sausage-man-monitor'],
  community: ['sausage-man-monitor'],
  'sausage-man-monitor': ['sausage-man-monitor'],
  support: ['filo-support-replies'],
  'filo-support-replies': ['filo-support-replies'],
  triage: ['filoai-feedback-triage'],
  'filoai-feedback-triage': ['filoai-feedback-triage'],
  poster: ['cindy-update-poster'],
  'cindy-update-poster': ['cindy-update-poster'],
  model: ['model-comparison-poster'],
  'model-comparison-poster': ['model-comparison-poster'],
  xiaohongshu: ['xiaohongshu-feedback-monitor'],
  'xiaohongshu-feedback-monitor': ['xiaohongshu-feedback-monitor'],
};

function fail(message) { console.error(`安装失败：${message}`); process.exit(1); }
function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function envOr(name, fallback = '') { return process.env[name] || fallback; }
function copyTree(source, destination, overwrite = false) {
  if (!fs.existsSync(source)) fail(`安装包缺少目录：${path.relative(packageRoot, source)}`);
  fs.mkdirSync(destination, { recursive: true });
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    if (['.DS_Store', '__pycache__'].includes(entry.name)) continue;
    const from = path.join(source, entry.name);
    const to = path.join(destination, entry.name);
    if (entry.isDirectory()) copyTree(from, to, overwrite);
    else if (overwrite || !fs.existsSync(to)) fs.copyFileSync(from, to);
  }
}
function writeNew(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  if (!fs.existsSync(file)) fs.writeFileSync(file, `${typeof value === 'string' ? value : JSON.stringify(value, null, 2) + '\n'}`, { mode: 0o600 });
}
async function ask(label, envName, fallback = '') {
  const value = envOr(envName, fallback);
  if (!interactive) return value;
  const input = (await rl.question(`${label}${fallback ? ` [${fallback}]` : ''}: `)).trim();
  return input || value || fallback;
}
function requireValue(value, label) {
  if (!value || value.startsWith('REPLACE_WITH_')) fail(`${label} 未配置`);
  return value;
}
function protectLocalData() {
  if (!fs.existsSync(path.join(target, '.git'))) return;
  const ignoreFile = path.join(target, '.gitignore');
  const entry = '.cindy/';
  const marker = '# Cindy workflow local data';
  const current = fs.existsSync(ignoreFile) ? fs.readFileSync(ignoreFile, 'utf8') : '';
  if (current.split(/\r?\n/).includes(entry)) return;
  const suffix = current === '' || current.endsWith('\n') ? '' : '\n';
  fs.writeFileSync(ignoreFile, `${current}${suffix}\n${marker}\n${entry}\n`, { mode: 0o644 });
}
function runPackageChecks() {
  execFileSync(process.execPath, [path.join(packageRoot, 'scripts', 'check-redaction.mjs')], { stdio: 'inherit' });
  execFileSync(process.execPath, [path.join(packageRoot, 'scripts', 'check-template-sync.mjs')], { stdio: 'inherit' });
}
function installSkill(name, overwrite = false) {
  copyTree(path.join(packageRoot, 'skills', name), path.join(target, '.agents', 'skills', name), overwrite);
}

function installCommunity() {
  runPackageChecks();
  const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const command = [path.join(packageRoot, 'skills', 'sausage-man-monitor', 'scripts', 'package_skill.py'),
    'install', '--target', path.join(target, '.agents', 'skills', 'sausage-man-monitor'), '--apply'];
  if (args.includes('--adopt-existing')) command.push('--adopt-existing');
  execFileSync(python, command, { stdio: 'inherit' });
}

async function installSupport() {
  const localRoot = path.join(target, '.cindy', 'filo-support-automation');
  const support = readJson(path.join(packageRoot, 'templates', 'config', 'support-policy.example.json'));
  support.automation.audit_log_path = path.join(localRoot, 'support-audit.jsonl');
  support.automation.intake_database_path = path.join(localRoot, 'intake.sqlite');
  if (interactive) {
    support.product = await ask('产品名称', 'CINDY_SUPPORT_PRODUCT', 'Filo');
    support.policy_review.reviewed_at = envOr('CINDY_SUPPORT_POLICY_REVIEWED_AT', new Date().toISOString().slice(0, 10));
    support.policy_review.reviewed_by = await ask('策略审核人', 'CINDY_SUPPORT_POLICY_REVIEWER');
    support.policy_review.source_of_truth = await ask('策略来源（内部路径或文档标识）', 'CINDY_SUPPORT_POLICY_SOURCE');
    support.sender.mailbox_account = await ask('Gmail 连接账号', 'CINDY_SUPPORT_GMAIL_ACCOUNT');
    support.sender.from_address = await ask('Gmail 发件别名', 'CINDY_SUPPORT_FROM_ADDRESS');
    support.sender.cc_addresses = [await ask('必需 CC 地址', 'CINDY_SUPPORT_CC_ADDRESS')];
    support.threading.staff_domains = [await ask('同事邮箱域名', 'CINDY_SUPPORT_STAFF_DOMAIN')];
    support.bug_tracking.canonical_repo = await ask('默认 GitHub 仓库（owner/repo）', 'CINDY_SUPPORT_FRONTEND_REPOSITORY');
    support.bug_tracking.repository_routes.frontend.repository = support.bug_tracking.canonical_repo;
    support.bug_tracking.repository_routes.server.repository = await ask('服务端 GitHub 仓库（owner/repo）', 'CINDY_SUPPORT_SERVER_REPOSITORY');
    for (const [value, label] of [[support.policy_review.reviewed_by, '策略审核人'], [support.policy_review.source_of_truth, '策略来源'], [support.sender.mailbox_account, 'Gmail 账号'], [support.sender.from_address, '发件别名'], [support.sender.cc_addresses[0], 'CC 地址'], [support.threading.staff_domains[0], '同事域名'], [support.bug_tracking.canonical_repo, '默认仓库'], [support.bug_tracking.repository_routes.server.repository, '服务端仓库']]) requireValue(value, label);
  }
  installSkill('filo-support-replies');
  writeNew(path.join(localRoot, 'support-policy.local.json'), support);
  writeNew(path.join(localRoot, 'README.local.txt'), '本目录包含本机配置、状态、审计和 SQLite 索引。不要提交或分享。\n');
  fs.mkdirSync(path.join(localRoot, 'state'), { recursive: true, mode: 0o700 });
  if (interactive) {
    execFileSync('python3', [path.join(target, '.agents', 'skills', 'filo-support-replies', 'scripts', 'validate_policy.py'), path.join(localRoot, 'support-policy.local.json')], { stdio: 'inherit' });
  } else {
    console.log('filo-support-replies：已安装脱敏配置模板，连接器和身份信息待在本机补齐。');
  }
  fs.copyFileSync(path.join(packageRoot, 'templates', 'schedules', 'support-replies.txt'), path.join(localRoot, 'support-replies.txt'));
}

async function installTriage() {
  const localRoot = path.join(target, '.cindy', 'filo-support-automation');
  const triage = readJson(path.join(packageRoot, 'templates', 'config', 'feedback-triage.example.json'));
  if (interactive) {
    triage.schedule.model = requireValue(await ask('可用模型标识', 'CINDY_TRIAGE_MODEL'), '模型标识');
    triage.schedule.providerId = requireValue(await ask('模型供应商标识', 'CINDY_TRIAGE_PROVIDER_ID'), '模型供应商标识');
    triage.sources.gmail.account = requireValue(await ask('Gmail 账号', 'CINDY_TRIAGE_GMAIL_ACCOUNT'), 'Gmail 账号');
    triage.sources.gmail.initialWatermarkTime = requireValue(await ask('Gmail 初始水位（ISO-8601）', 'CINDY_TRIAGE_GMAIL_WATERMARK'), 'Gmail 初始水位');
    triage.sources.feishu.chatName = requireValue(await ask('Feishu 群名称', 'CINDY_TRIAGE_FEISHU_CHAT_NAME'), 'Feishu 群名称');
    triage.sources.feishu.chatId = requireValue(await ask('Feishu 群 ID', 'CINDY_TRIAGE_FEISHU_CHAT_ID'), 'Feishu 群 ID');
    triage.sources.feishu.initialWatermarkPosition = requireValue(await ask('Feishu 初始位置', 'CINDY_TRIAGE_FEISHU_POSITION'), 'Feishu 初始位置');
    triage.sources.feishu.initialWatermarkMessageId = requireValue(await ask('Feishu 初始消息 ID', 'CINDY_TRIAGE_FEISHU_MESSAGE_ID'), 'Feishu 初始消息 ID');
    triage.sources.feishu.initialWatermarkTime = requireValue(await ask('Feishu 初始水位（ISO-8601）', 'CINDY_TRIAGE_FEISHU_WATERMARK'), 'Feishu 初始水位');
  }
  triage.insights.databasePath = path.join(localRoot, 'intake.sqlite');
  triage.state.shadowFile = path.join(localRoot, 'state', 'feedback-triage-shadow.json');
  triage.state.liveFile = path.join(localRoot, 'state', 'feedback-triage-live.json');
  installSkill('filoai-feedback-triage');
  writeNew(path.join(localRoot, 'feedback-triage.local.json'), triage);
  fs.mkdirSync(path.join(localRoot, 'state'), { recursive: true, mode: 0o700 });
  fs.copyFileSync(path.join(packageRoot, 'templates', 'schedules', 'feedback-triage.txt'), path.join(localRoot, 'feedback-triage.txt'));
  if (interactive) {
    execFileSync(process.execPath, [path.join(target, '.agents', 'skills', 'filoai-feedback-triage', 'scripts', 'validate-config.mjs'), path.join(localRoot, 'feedback-triage.local.json')], { stdio: 'inherit' });
  } else {
    console.log('filoai-feedback-triage：已安装脱敏配置模板，连接器和水位待在本机补齐。');
  }
}

function installPoster() {
  const workflow = 'cindy-update-poster';
  const localRoot = path.join(target, '.cindy', 'workflows', workflow);
  installSkill(workflow, true);
  copyTree(path.join(packageRoot, 'workflows', workflow), localRoot, true);
  const config = readJson(path.join(packageRoot, 'templates', 'config', `${workflow}.example.json`));
  config.client_repo = envOr('CINDY_POSTER_CLIENT_REPO', config.client_repo);
  config.server_repo = envOr('CINDY_POSTER_SERVER_REPO', config.server_repo);
  config.timezone = envOr('CINDY_POSTER_TIMEZONE', config.timezone);
  config.chrome = envOr('CINDY_POSTER_CHROME', config.chrome);
  config.background_dir = envOr('CINDY_POSTER_BACKGROUND_DIR', config.background_dir);
  writeNew(path.join(localRoot, 'config.local.json'), config);
  fs.mkdirSync(path.join(localRoot, 'content'), { recursive: true, mode: 0o700 });
  fs.mkdirSync(path.join(localRoot, 'out'), { recursive: true, mode: 0o700 });
  fs.copyFileSync(path.join(packageRoot, 'templates', 'schedules', `${workflow}.txt`), path.join(localRoot, `${workflow}.txt`));
  execFileSync(process.execPath, [path.join(packageRoot, 'scripts', 'check-package.mjs')], { stdio: 'inherit' });
}

function installModelComparisonPoster() {
  const workflow = 'model-comparison-poster';
  const localRoot = path.join(target, '.cindy', 'workflows', workflow);
  installSkill(workflow, true);
  copyTree(path.join(packageRoot, 'workflows', workflow), localRoot, true);
  const config = readJson(path.join(packageRoot, 'templates', 'config', `${workflow}.example.json`));
  config.asset_dir = envOr('MODEL_POSTER_ASSET_DIR', config.asset_dir);
  config.hero_image = envOr('MODEL_POSTER_HERO_IMAGE', config.hero_image);
  config.catalog_url = envOr('MODEL_POSTER_CATALOG_URL', config.catalog_url);
  config.chrome = envOr('CINDY_POSTER_CHROME', config.chrome);
  writeNew(path.join(localRoot, 'config.local.json'), config);
  fs.mkdirSync(path.join(localRoot, 'content'), { recursive: true, mode: 0o700 });
  fs.mkdirSync(path.join(localRoot, 'out'), { recursive: true, mode: 0o700 });
  fs.copyFileSync(path.join(packageRoot, 'templates', 'schedules', `${workflow}.txt`), path.join(localRoot, `${workflow}.txt`));
}

function installXiaohongshu() {
  const workflow = 'xiaohongshu-feedback-monitor';
  const localRoot = path.join(target, '.cindy', 'workflows', workflow);
  installSkill(workflow);
  const config = readJson(path.join(packageRoot, 'templates', 'config', 'xiaohongshu-feedback.example.json'));
  config.runtime.directory = `.cindy/workflows/${workflow}`;
  config.browser.chromeLocalState = process.platform === 'darwin'
    ? path.join(process.env.HOME || '', 'Library/Application Support/Google/Chrome/Local State')
    : 'REPLACE_WITH_LOCAL_CHROME_STATE_PATH';
  writeNew(path.join(localRoot, 'config.local.json'), config);
  writeNew(path.join(localRoot, 'README.local.txt'), '本目录包含本机账号映射、增量状态和报告。不要提交或分享。\n');
  const manage = path.join(target, '.agents', 'skills', workflow, 'scripts', 'manage_config.py');
  execFileSync('python3', [manage, 'init', '--runtime', localRoot, '--slots', String(config.accountSlots), '--disabled'], { stdio: 'inherit' });
  for (const file of [`${workflow}.txt`, `${workflow}.yaml`]) fs.copyFileSync(path.join(packageRoot, 'templates', 'schedules', file), path.join(localRoot, file));
}

if (!workflowAliases[workflowArg]) fail(`未知 workflow：${workflowArg}。可选：all、filo-support-replies、filoai-feedback-triage、cindy-update-poster、model-comparison-poster、xiaohongshu-feedback-monitor、community`);
if (!fs.existsSync(target) || !fs.statSync(target).isDirectory()) fail(`目标目录不存在：${target}`);
protectLocalData();
const selected = workflowAliases[workflowArg];
if (selected.includes('filo-support-replies')) await installSupport();
if (selected.includes('filoai-feedback-triage')) await installTriage();
if (selected.includes('cindy-update-poster')) installPoster();
if (selected.includes('model-comparison-poster')) installModelComparisonPoster();
if (selected.includes('xiaohongshu-feedback-monitor')) installXiaohongshu();
if (selected.includes('sausage-man-monitor')) installCommunity();
runPackageChecks();
console.log(`安装完成：${target}`);
console.log(`已安装工作流：${selected.join('、')}`);
console.log(selected.length === 1 && selected[0] === 'sausage-man-monitor'
  ? '下一步：按 Skill 的 references/install.md 配置工作台地址并运行 doctor；没有创建业务任务或调度。'
  : '下一步：在 Cindy 中连接所需 Gmail、Feishu、GitHub 或浏览器连接器，再使用目标目录 .cindy/ 下对应的 schedule 模板创建独立、默认暂停的定时任务。安装器不会写入线上 Scheduler 或凭证。');
if (!interactive) console.log('模板模式：仅写入脱敏模板和本地运行目录，未写入账号、凭证或远程任务；如需安装时填写本机配置，请加 --interactive。');
rl?.close();
