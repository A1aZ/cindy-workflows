"""Seal, verify, package and update the same Skill folder for GitHub and Cindy."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid
import zipfile

NAME = 'sausage-man-monitor'
ROOT = Path(__file__).resolve().parents[1]
FILES = ('SKILL.md', 'agents/openai.yaml', 'assets/config.example.json',
         'references/capabilities.md', 'references/host-workflows.md', 'references/install.md',
         'scripts/query.py', 'scripts/package_skill.py')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def ordinary(path):
    return not path.is_symlink() and not (hasattr(path, 'is_junction') and path.is_junction())


def managed_path(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or name.startswith('/') or any(part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('包清单包含无效的相对路径。')
    path = root / name
    for item in [path, *path.parents]:
        if item == root:
            break
        if not ordinary(item):
            raise ValueError('包文件不能通过链接写到目录外：' + name)
    return path


def verify(root, strict=True):
    root = Path(root).resolve()
    value = read(managed_path(root, 'PACKAGE.json'))
    if value.get('schema') != 'community.skill.package.v1' or value.get('name') != NAME:
        raise ValueError('包身份不匹配。')
    if not isinstance(value.get('files'), dict) or not value['files'] or (strict and set(value['files']) != set(FILES)):
        raise ValueError('包文件清单不完整或包含未知文件。')
    changed = [name for name, expected in value['files'].items()
               if not managed_path(root, name).is_file() or digest(root / name) != expected]
    if changed:
        raise ValueError('包文件与版本清单不一致（存在本地修改或缺失）：' + ', '.join(changed))
    return value


def seal(root, version):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('版本格式应为 x.y.z。')
    text = (root / 'SKILL.md').read_text(encoding='utf-8')
    text, count = re.subn(r'(?m)^  version: "[^"]+"$', '  version: "' + version + '"', text)
    if count != 1:
        raise ValueError('SKILL.md 需要唯一的 metadata.version。')
    (root / 'SKILL.md').write_text(text, encoding='utf-8', newline='\n')
    value = {'schema': 'community.skill.package.v1', 'name': NAME, 'version': version,
             'files': {name: digest(managed_path(root, name)) for name in FILES}}
    write(root / 'PACKAGE.json', value)
    return value


def target_path(value):
    target = Path(value).expanduser().resolve()
    if target.name != NAME:
        raise ValueError('--target 必须是最终的 sausage-man-monitor 文件夹。')
    return target


def old_files(target, adopt):
    if (target / 'PACKAGE.json').exists():
        manifest = verify(target, strict=False)
        return [*manifest['files'], 'PACKAGE.json']
    if target.exists() and any(target.iterdir()) and not adopt:
        raise ValueError('现有目录没有版本清单；先预览，再明确 --adopt-existing 以备份并接管旧副本。')
    return [name for name in FILES if managed_path(target, name).is_file()]


def remove_stage(stage, parent):
    # Only remove our checked, freshly-created staging directory in the target parent.
    if stage.exists():
        if stage.resolve().parent != parent.resolve() or not stage.name.startswith('.sausage-man-monitor-stage-'):
            raise ValueError('暂存路径超出预期目录。')
        shutil.rmtree(stage)


def stage_copy(target):
    stage = Path(tempfile.mkdtemp(prefix='.sausage-man-monitor-stage-', dir=target.parent))
    if target.exists():
        shutil.copytree(target, stage, dirs_exist_ok=True, symlinks=True)
    return stage


def install(source, destination, apply=False, adopt=False):
    source, target = Path(source).resolve(), target_path(destination)
    if source == target:
        return {'ok': True, 'action': 'already_source', 'version': verify(source)['version'], 'target': str(target)}
    manifest = verify(source)
    old = old_files(target, adopt)
    new = [*manifest['files'], 'PACKAGE.json']
    changes = {'add': [], 'update': [], 'remove': sorted(set(old) - set(new))}
    for name in new:
        path = managed_path(target, name)
        if not path.exists():
            changes['add'].append(name)
        elif digest(path) != digest(source / name):
            changes['update'].append(name)
    result = {'ok': True, 'action': 'install' if apply else 'preview', 'version': manifest['version'],
              'target': str(target), 'changes': changes, 'personal_config': 'outside_skill_preserved'}
    if not apply or not any(changes.values()):
        result['changed'] = False
        return result
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = stage_copy(target)
    backup = None
    try:
        for name in changes['remove']:
            managed_path(stage, name).unlink()
        for name in new:
            path = managed_path(stage, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, path)
        verify(stage)
        if target.exists():
            backup = target.parent / ('.' + NAME + '-backups') / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
            backup.mkdir(parents=True)
            receipt = {'schema': 'community.skill.backup.v1', 'target': str(target),
                       'old_files': {name: digest(managed_path(target, name)) for name in old},
                       'installed_manifest_sha256': digest(source / 'PACKAGE.json')}
            write(backup / 'receipt.json', receipt)
            # Both source and destination were resolved within this target parent.
            target.rename(backup / 'files')
        try:
            stage.rename(target)
        except OSError:
            if backup and (backup / 'files').exists() and not target.exists():
                (backup / 'files').rename(target)
            raise
        result.update(changed=True, backup=str(backup) if backup else None,
                      package_sha256=digest(target / 'PACKAGE.json'))
        return result
    finally:
        remove_stage(stage, target.parent)


def rollback(destination, backup_value, apply=False):
    target = target_path(destination)
    backup = Path(backup_value).expanduser().resolve()
    if backup.parent != target.parent / ('.' + NAME + '-backups'):
        raise ValueError('备份不属于此 Skill 的备份目录。')
    receipt = read(backup / 'receipt.json')
    if receipt.get('schema') != 'community.skill.backup.v1' or Path(receipt['target']) != target:
        raise ValueError('备份回执与目标不匹配。')
    current = verify(target, strict=False)
    if digest(target / 'PACKAGE.json') != receipt['installed_manifest_sha256']:
        raise ValueError('当前版本不是这个备份对应的升级版本。')
    for name, expected in receipt['old_files'].items():
        if digest(managed_path(backup / 'files', name)) != expected:
            raise ValueError('旧备份内容已改变：' + name)
    result = {'ok': True, 'action': 'rollback' if apply else 'preview_rollback', 'target': str(target), 'backup': str(backup)}
    if not apply:
        return result
    replaced = backup / 'rollback-replaced'
    if replaced.exists():
        raise ValueError('这个备份已执行过回退。')
    stage = stage_copy(target)
    try:
        for name in set([*current['files'], 'PACKAGE.json']) - set(receipt['old_files']):
            managed_path(stage, name).unlink(missing_ok=True)
        for name in receipt['old_files']:
            path = managed_path(stage, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup / 'files' / name, path)
        if (stage / 'PACKAGE.json').exists():
            verify(stage, strict=False)
        target.rename(replaced)
        try:
            stage.rename(target)
        except OSError:
            if not target.exists():
                replaced.rename(target)
            raise
        return result
    finally:
        remove_stage(stage, target.parent)


def pack(root, output):
    value = verify(root)
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Small source-only package: stored entries avoid zlib-version differences.
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as archive:
        for name in sorted([*value['files'], 'PACKAGE.json']):
            info = zipfile.ZipInfo(NAME + '/' + name, date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (root / name).read_bytes())
    return {'ok': True, 'version': value['version'], 'output': str(output), 'sha256': digest(output), 'files': len(value['files']) + 1}


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('verify')
    sub.add_parser('seal').add_argument('--version', required=True)
    sub.add_parser('pack').add_argument('--output', required=True)
    install_parser = sub.add_parser('install')
    install_parser.add_argument('--target', required=True)
    install_parser.add_argument('--apply', action='store_true')
    install_parser.add_argument('--adopt-existing', action='store_true')
    restore = sub.add_parser('rollback')
    restore.add_argument('--target', required=True)
    restore.add_argument('--backup', required=True)
    restore.add_argument('--apply', action='store_true')
    args = p.parse_args()
    try:
        if args.command == 'verify':
            manifest = verify(ROOT)
            result = {'ok': True, 'version': manifest['version'], 'files': len(manifest['files']), 'package_sha256': digest(ROOT / 'PACKAGE.json')}
        elif args.command == 'seal':
            result = {'ok': True, 'version': seal(ROOT, args.version)['version']}
        elif args.command == 'pack':
            result = pack(ROOT, args.output)
        elif args.command == 'install':
            result = install(ROOT, args.target, args.apply, args.adopt_existing)
        else:
            result = rollback(args.target, args.backup, args.apply)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
