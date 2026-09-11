"""Conservative ASCII/ZIP20 package contract for legacy Fluffy versions."""
import hashlib
import re
import zipfile
from pathlib import Path, PurePosixPath


def package_name(source, target, build_id):
    stem = Path(source).stem
    slug = re.sub(r'[^A-Za-z0-9_-]+', '-', stem).strip('-')[:40]
    if not stem.isascii() or not slug:
        slug = 'Character-' + hashlib.sha256(stem.encode('utf-8')).hexdigest()[:8]
    target = re.sub(r'[^A-Za-z0-9_-]', '', target) or 'Character'
    return f'{slug}-{target}-{build_id[:12]}'


def write_package(entries, output):
    output = Path(output)
    folder = output.stem
    if not folder.isascii() or not re.fullmatch(r'[A-Za-z0-9_-]+', folder):
        raise ValueError('Package name must be ASCII letters, numbers, hyphens or underscores')
    entries = dict(entries)
    if 'modinfo.ini' not in entries or not any(p.startswith('natives/') for p in entries):
        raise ValueError('Missing modinfo.ini or natives payload')
    # ASCII is also valid ANSI on every Windows code page. Never rewrite assets.
    manifest = entries['modinfo.ini'].decode('utf-8-sig')
    lines = [line for line in manifest.splitlines() if not line.lower().startswith('name=')]
    entries['modinfo.ini'] = ('name=' + folder + '\r\n' + '\r\n'.join(lines) + '\r\n').encode('ascii', errors='replace')
    seen = set()
    for rel in entries:
        path = PurePosixPath(rel)
        if (not rel.isascii() or '\\' in rel or ':' in rel or path.is_absolute()
                or '..' in path.parts or str(path) != rel or rel.lower() in seen):
            raise ValueError(f'Unsafe or incompatible archive path: {rel}')
        seen.add(rel.lower())
    hashes = {p: hashlib.sha256(data).hexdigest() for p, data in entries.items()}
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, allowZip64=False) as z:
        for rel, data in sorted(entries.items()):
            z.writestr(folder + '/' + rel, data)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            raise ValueError('Archive CRC failure')
        for info in z.infolist():
            if info.flag_bits or info.extract_version > 20 or info.compress_type != 8:
                raise ValueError('Incompatible ZIP header')
            rel = info.filename[len(folder) + 1:]
            if hashlib.sha256(z.read(info)).hexdigest() != hashes[rel]:
                raise ValueError('Archive payload mismatch')
    return hashes


def package_directory(stage, output):
    stage = Path(stage)
    return write_package({p.relative_to(stage).as_posix(): p.read_bytes()
                          for p in stage.rglob('*') if p.is_file()}, output)


def repair_archive(source, output):
    with zipfile.ZipFile(source) as z:
        if z.testzip() is not None:
            raise ValueError('Source ZIP is damaged')
        files = [i for i in z.infolist() if not i.is_dir()]
        roots = {i.filename.split('/')[0] for i in files}
        if len(roots) != 1:
            raise ValueError('Expected one package root')
        entries = {}
        for i in files:
            rel = i.filename.split('/', 1)[1]
            if rel in entries:
                raise ValueError('Duplicate member')
            entries[rel] = z.read(i)
    return write_package(entries, output)
