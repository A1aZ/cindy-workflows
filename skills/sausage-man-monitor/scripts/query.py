"""Portable read-only community workbench client (Python 3.10+, standard library)."""
import argparse
import hashlib
import json
import math
import ntpath
import os
from pathlib import Path
import re
import sys
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, unquote
from urllib.request import ProxyHandler, HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
ROUTES = {
    'snapshot': '/api/snapshot', 'manifest': '/api/export/manifest',
    'state': '/api/workflow/state', 'batches': '/api/workflow/feedback/batches',
    'todos': '/api/todos', 'review': '/api/topic-review',
    'backups': '/api/workflow/review-backups',
}
DATASETS = ('metrics', 'content', 'activities', 'schedule', 'analysis',
            'article_daily', 'reading_sources', 'article_history')
COUNT_NOTE = '索引反馈数不等于发布的反馈总分母；all 范围也包含非反馈。'


class WorkbenchError(ValueError):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def require(condition, message, kind='contract_mismatch'):
    if not condition:
        raise WorkbenchError(kind, message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def validate_base(value):
    url = urlsplit(value)
    require(url.scheme in ('http', 'https') and bool(url.hostname),
            '工作台地址必须是完整的 http(s) 地址。', 'configuration')
    require(not url.username and not url.password and not url.query and not url.fragment,
            '连接地址不能包含账号、凭据、查询参数或锚点。', 'configuration')
    require(url.port is None or 0 < url.port < 65536, '端口无效。', 'configuration')
    return value.rstrip('/')


def settings(args):
    explicit = args.config or os.environ.get('SAUSAGE_WORKBENCH_CONFIG')
    path = Path(explicit).expanduser() if explicit else Path.home() / '.config/sausage-man-monitor/config.json'
    require(not explicit or path.is_file() or args.command == 'configure',
            '指定的配置文件不存在。', 'configuration')
    data = read_json(path) if path.is_file() else {}
    require(isinstance(data, dict), '配置必须是 JSON 对象。', 'configuration')
    base = args.base_url or os.environ.get('SAUSAGE_WORKBENCH_URL') or data.get('base_url') or 'http://127.0.0.1:8777'
    timeout = args.timeout if args.timeout is not None else data.get('timeout', 30)
    require(isinstance(timeout, (int, float)) and math.isfinite(timeout) and 0 < timeout <= 300,
            'timeout 应为 0 到 300 秒之间的正数。', 'configuration')
    return path, {**data, 'base_url': validate_base(base), 'timeout': timeout}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise WorkbenchError('redirect', '工作台返回重定向；请配置最终地址后重新查询。')


class Client:
    def __init__(self, base, timeout=30):
        self.base, self.timeout = validate_base(base), timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def url(self, path):
        return self.base + path

    def raw(self, path, **params):
        url = self.url(path) + ('?' + urlencode(params) if params else '')
        with self.opener.open(url, timeout=self.timeout) as response:
            return response.read()

    def get(self, path, **params):
        result = json.loads(self.raw(path, **params))
        require(isinstance(result, dict), '服务没有返回预期的 JSON 对象。')
        return result

    def batches(self):
        data = self.get(ROUTES['batches'])
        require(isinstance(data.get('batches'), list) and bool(data.get('current_snapshot')), '批次接口缺少发布身份。')
        return data

    def select_batch(self, data, identifier=''):
        rows = [b for b in data['batches'] if (b['id'] == identifier if identifier else b['current'])]
        require(len(rows) == 1, '批次缺失或不唯一，请从 batches 选择实际 ID。', 'batch_unavailable')
        require(bool(rows[0].get('snapshot')), '批次缺少 snapshot。')
        return rows[0]

    def check_pin(self, initial, batch):
        after = self.batches()
        selected = self.select_batch(after, batch['id'])
        require(after['current_snapshot'] == initial['current_snapshot'] and selected['snapshot'] == batch['snapshot'],
                '发布在读取期间发生变化；此次结果未交付，请重新查询。', 'publication_changed')

    def summary(self):
        snap, batches = self.get(ROUTES['snapshot']), self.batches()
        publication = snap['publication']
        sha = publication['snapshot']['sha256']
        require(batches['current_snapshot'] == sha, '发布与批次不是同一快照，请重新查询。', 'publication_changed')
        current = self.select_batch(batches)
        return {'version': snap.get('version'), 'snapshot_sha256': sha,
                'meta': snap.get('meta'), 'publication': publication, 'batches': batches,
                'human_review': snap.get('human_review'),
                'index_coverage': {'source_count': current.get('source_count'),
                                   'indexed_feedback_count': current.get('feedback_count'), 'note': COUNT_NOTE}}

    def search(self, args):
        require(not args.all or args.page == 0, '--all 必须从第 0 页开始。', 'arguments')
        require(0 <= args.page <= 10000 and 1 <= args.max_pages <= 10001, '页码或页数上限无效。', 'arguments')
        require(len(args.q) <= 100, '查询文本不能超过 100 字。', 'arguments')
        for day in (args.start, args.end):
            require(not day or date.fromisoformat(day).isoformat() == day, '日期格式应为 YYYY-MM-DD。', 'arguments')
        require(not (args.start and args.end) or args.start <= args.end, '起始日不能晚于结束日。', 'arguments')
        initial = self.batches()
        batch = self.select_batch(initial, args.batch)
        page, gathered, seen, total, pages = args.page, [], set(), None, 0
        while True:
            result = self.get('/api/workflow/feedback/search', batch=batch['id'], q=args.q, kind=args.kind,
                              start=args.start, end=args.end, topic=args.topic, page=page, scope=args.scope)
            require(result.get('batch') == batch['id'] and result.get('page') == page, '返回的批次或页码不一致。')
            require(isinstance(result.get('total'), int) and result['total'] >= 0 and result.get('page_size') == 20
                    and isinstance(result.get('sources'), list), '检索分页契约不匹配。')
            if total is None:
                total = result['total']
            require(result['total'] == total, '分页总数发生变化，请重新查询。', 'publication_changed')
            expected = max(0, min(20, total - page * 20))
            require(len(result['sources']) == expected, '返回来源数量与分页总数不一致。')
            for source in result['sources']:
                require(source['id'] not in seen, '分页存在重复来源，不能声称读取完整。')
                seen.add(source['id'])
                gathered.append(source)
            pages += 1
            self.check_pin(initial, batch)
            if not args.all or (page + 1) * 20 >= total:
                break
            require(pages < args.max_pages, '达到 --max-pages 上限；未返回截断结果，请缩小条件或提高上限。', 'page_limit')
            page += 1
        return {**result, 'page': args.page, 'sources': gathered, 'pages_read': pages,
                'returned': len(gathered), 'complete': args.page == 0 and len(gathered) == total,
                'snapshot_sha256': batch['snapshot'], 'current_snapshot': initial['current_snapshot'],
                'scope': args.scope, 'limits': batch.get('limits', []), 'count_note': COUNT_NOTE}

    def originals(self, ids_text, snapshot=None):
        ids = [part.strip() for part in ids_text.split(',')]
        require(1 <= len(ids) <= 20 and all(ids) and len(set(ids)) == len(ids),
                '--ids 需要 1–20 个不同且非空的来源 ID。', 'arguments')
        initial = self.batches()
        sha = snapshot or initial['current_snapshot']
        require(sha == initial['current_snapshot'], '原文接口仅支持当前快照；历史全文请查对应批次的 search。', 'snapshot_unavailable')
        result = self.get('/api/workflow/feedback/originals', snapshot=sha, ids=','.join(ids))
        require(result.get('snapshot_sha256') == sha and set(result.get('sources', {})) == set(ids), '原文快照或来源 ID 不一致。')
        self.check_pin(initial, self.select_batch(initial))
        return result

    def reports(self):
        state = self.get(ROUTES['state'])
        require(state.get('contract') == 'project.report.v1', '运营报表契约不受支持。')
        rows = []
        for row in state['reports']:
            # These are the existing server/UI download routes, using an actual published ID.
            root = '/reports/download/' + quote(row['id'], safe='') + '/'
            rows.append({**row, 'downloads': {name: self.url(root + filename) for name, filename in
                         [('json', 'REPORT.json'), ('html', 'index.html'), ('markdown', 'REPORT.md')]}})
        return {'reports': rows, 'count': len(rows), 'contract': state['contract']}

    def download_path(self, value):
        base = urlsplit(self.base)
        parsed = urlsplit(self.url(value) if value.startswith('/') and not value.startswith('//') else value)
        require((parsed.scheme, parsed.netloc) == (base.scheme, base.netloc) and not parsed.fragment and not parsed.query,
                '仅下载本工作台的媒体或报表地址。', 'arguments')
        prefix = base.path.rstrip('/')
        require(parsed.path.startswith(prefix + '/'), '下载地址不在配置的工作台路径内。', 'arguments')
        path = parsed.path[len(prefix):]
        decoded = unquote(path)
        require(path.startswith(('/media/', '/reports/download/')) and '\\' not in decoded
                and not any(part in ('.', '..') for part in decoded.split('/')), '下载路径不是已支持的媒体/报表路由。', 'arguments')
        return path


def link_index(data, client):
    urls, host_paths = set(), set()
    def walk(value):
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str):
            if value.startswith(('http://', 'https://')) and not any(c.isspace() for c in value):
                urls.add(value)
            elif value.startswith(('/media/', '/reports/', '/api/')):
                urls.add(client.url(value))
            elif ntpath.splitdrive(value)[0] or value.startswith('/'):
                host_paths.add(value)
    walk(data)
    return {'data': data, 'links': sorted(urls), 'host_only_paths': sorted(host_paths)}


def save_new(path, content):
    path = Path(path).expanduser().resolve()
    require(not path.exists(), '输出文件已存在；请使用新的文件名。', 'output_exists')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(content)
    return str(path)


def doctor(client, config, path, host=False):
    from package_skill import verify
    manifest = verify(ROOT)
    summary = client.summary()
    state = client.get(ROUTES['state'])
    require(state.get('schema') == 'project.workflow.state.v1' and state.get('contract') == 'project.report.v1', '运营工作台接口契约不匹配。')
    result = {'ok': True, 'skill_version': manifest['version'], 'python': sys.version.split()[0],
              'config_path': str(path), 'base_url': client.base,
              'release_id': summary['publication'].get('release_id'), 'snapshot_sha256': summary['snapshot_sha256'],
              'report_count': len(state['reports']), 'checks': ['package_hashes', 'snapshot', 'batches', 'workflow_state'],
              'network_note': '这是当前执行端的连通性验证，不代表另一台电脑已验收。'}
    if host:
        root = Path(config.get('project_root') or '.')
        required = ['AGENTS.md', 'HANDOFF.md', 'workflow/PITFALLS.md', 'workflow/AGENT-HANDOFF.md', 'scripts/project-workflow.ps1']
        missing = [name for name in required if not (root / name).is_file()]
        require(bool(config.get('project_root')) and not missing, '主机工作流未就绪；需配置完整项目根。缺失：' + ', '.join(missing), 'host_unavailable')
        result['checks'].append('host_files')
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url')
    p.add_argument('--config')
    p.add_argument('--timeout', type=float)
    p.add_argument('--links', action='store_true')
    sub = p.add_subparsers(dest='command', required=True)
    for name in (*ROUTES, 'summary', 'reports'):
        sub.add_parser(name)
    sub.add_parser('doctor').add_argument('--host', action='store_true')
    conf = sub.add_parser('configure')
    conf.add_argument('--base-url', dest='configure_url')
    conf.add_argument('--project-root')
    search = sub.add_parser('search')
    for name in ('batch', 'q', 'start', 'end', 'topic'):
        search.add_argument('--' + name, default='')
    search.add_argument('--kind', choices=('', 'review', 'topic'), default='')
    search.add_argument('--scope', choices=('feedback', 'all'), default='feedback')
    search.add_argument('--page', type=int, default=0)
    search.add_argument('--all', action='store_true')
    search.add_argument('--max-pages', type=int, default=200)
    original = sub.add_parser('originals')
    original.add_argument('--ids', required=True)
    original.add_argument('--snapshot')
    for name in ('report', 'action', 'inputs'):
        child = sub.add_parser(name)
        child.add_argument('--id', required=True, **({'choices': DATASETS} if name == 'inputs' else {}))
    sub.add_parser('coverage').add_argument('--month')
    history = sub.add_parser('history')
    history.add_argument('--kind', default='')
    history.add_argument('--before', type=int, default=0)
    related = sub.add_parser('action-links')
    related.add_argument('--platform', default='')
    related.add_argument('--activity', default='')
    sub.add_parser('export').add_argument('--output')
    download = sub.add_parser('download')
    download.add_argument('--url', required=True)
    download.add_argument('--output', required=True)
    download.add_argument('--sha256')
    return p


def run(args):
    path, config = settings(args)
    if args.command == 'configure':
        config['base_url'] = validate_base(args.configure_url or config['base_url'])
        if args.project_root is not None:
            config['project_root'] = str(Path(args.project_root).expanduser().resolve())
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        os.replace(temp, path)
        return {'ok': True, 'config_path': str(path), 'base_url': config['base_url']}
    c, cmd = Client(config['base_url'], config['timeout']), args.command
    if cmd in ROUTES:
        result = c.get(ROUTES[cmd])
    elif cmd == 'summary':
        result = c.summary()
    elif cmd == 'doctor':
        result = doctor(c, config, path, args.host)
    elif cmd == 'search':
        result = c.search(args)
    elif cmd == 'originals':
        result = c.originals(args.ids, args.snapshot)
    elif cmd == 'reports':
        result = c.reports()
    elif cmd in ('report', 'action', 'inputs'):
        prefix = {'report': 'report', 'action': 'actions', 'inputs': 'inputs'}[cmd]
        result = c.get('/api/workflow/' + prefix + '/' + quote(args.id, safe=''))
    elif cmd == 'coverage':
        require(not args.month or bool(re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', args.month)), '月份格式应为 YYYY-MM。', 'arguments')
        result = c.get('/api/workflow/source-status', **({'month': args.month} if args.month else {}))
    elif cmd == 'history':
        result = c.get('/api/workflow/review-history', kind=args.kind, before=args.before)
    elif cmd == 'action-links':
        result = c.get('/api/workflow/action-links', platform=args.platform, activity=args.activity)
    elif cmd == 'export':
        manifest = c.get(ROUTES['manifest'])
        raw = c.raw('/api/export')
        require(hashlib.sha256(raw).hexdigest() == manifest['sha256'], '导出与清单哈希不一致，请重新查询。', 'publication_changed')
        data = json.loads(raw)
        result = {'manifest': manifest, 'data': data} if not args.output else {
            'ok': True, 'output': save_new(args.output, raw), 'bytes': len(raw), 'manifest': manifest, 'sha256_verified': True}
    elif cmd == 'download':
        route = c.download_path(args.url)
        raw = c.raw(route)
        digest = hashlib.sha256(raw).hexdigest()
        require(not args.sha256 or args.sha256.lower() == digest, '下载文件与指定 SHA256 不一致。', 'hash_mismatch')
        result = {'ok': True, 'output': save_new(args.output, raw), 'url': c.url(route), 'bytes': len(raw),
                  'sha256': digest, 'expected_sha256_verified': bool(args.sha256)}
    else:
        raise WorkbenchError('arguments', '未知命令。')
    return link_index(result, c) if args.links else result


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    args = parser().parse_args()
    try:
        result = run(args)
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError) as exc:
        status = getattr(exc, 'code', None)
        kind = getattr(exc, 'kind', 'http_error' if status else 'connection' if isinstance(exc, (URLError, TimeoutError, ConnectionError)) else 'invalid_data')
        hints = {403: '服务拒绝当前访问来源；检查现有网络访问权限。', 404: '接口、版本或文件不存在。',
                 409: '发布或数据冲突；重新核对版本。', 503: '服务存储或发布绑定暂不可用。'}
        print(json.dumps({'ok': False, 'kind': kind, 'error': str(exc), 'http_status': status,
                          'hint': hints.get(status, '检查配置和服务状态；不会自动启动或重建工作台。')}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
