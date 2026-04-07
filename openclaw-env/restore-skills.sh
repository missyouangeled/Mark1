#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="${WORKSPACE_DIR}/skills"
MANIFEST="${WORKSPACE_DIR}/openclaw-env/skills-manifest.json"

mkdir -p "${SKILLS_DIR}"

export WORKSPACE_DIR
export SKILLS_DIR
export MANIFEST

python3 - <<'PY'
import json, os, shutil, subprocess, tempfile, zipfile, pathlib, urllib.request

workspace = pathlib.Path(os.environ.get('WORKSPACE_DIR', ''))
skills_dir = pathlib.Path(os.environ.get('SKILLS_DIR', ''))
manifest_path = pathlib.Path(os.environ.get('MANIFEST', ''))
manifest = json.loads(manifest_path.read_text())

for skill in manifest.get('skills', []):
    name = skill['name']
    dst = skills_dir / name
    print(f'== restoring {name} ==')

    if dst.exists():
        print(f'  skip: already exists -> {dst}')
        continue

    stype = skill['type']
    if stype == 'git':
        subprocess.run([
            'git', 'clone', '--depth=1', '--branch', skill.get('branch', 'main'), skill['repo'], str(dst)
        ], check=True)
        git_dir = dst / '.git'
        if git_dir.exists():
            shutil.rmtree(git_dir)
        print(f'  restored from git: {skill["repo"]}')

    elif stype == 'github-zip':
        with urllib.request.urlopen(skill['zipUrl']) as r:
            data = r.read()
        fd, zip_path = tempfile.mkstemp(suffix='.zip')
        os.close(fd)
        pathlib.Path(zip_path).write_bytes(data)
        extract_dir = pathlib.Path(tempfile.mkdtemp(prefix='skill-restore-'))
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)
        root = next(extract_dir.iterdir())
        shutil.copytree(root, dst)
        git_dir = dst / '.git'
        if git_dir.exists():
            shutil.rmtree(git_dir)
        os.remove(zip_path)
        shutil.rmtree(extract_dir)
        print(f'  restored from zip: {skill["zipUrl"]}')

    elif stype == 'clawhub-download':
        with urllib.request.urlopen(skill['downloadUrl']) as r:
            data = r.read()
        fd, zip_path = tempfile.mkstemp(suffix='.zip')
        os.close(fd)
        pathlib.Path(zip_path).write_bytes(data)
        extract_dir = pathlib.Path(tempfile.mkdtemp(prefix='skill-restore-'))
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)
        shutil.copytree(extract_dir, dst)
        os.remove(zip_path)
        shutil.rmtree(extract_dir)
        print(f'  restored from ClawHub download: {skill["slug"]}')

    elif stype == 'clawhub':
        subprocess.run(['clawhub', '--workdir', str(workspace), 'install', skill['slug']], check=True)
        print(f'  restored via clawhub: {skill["slug"]}')

    else:
        raise RuntimeError(f'unknown skill type: {stype}')
PY
