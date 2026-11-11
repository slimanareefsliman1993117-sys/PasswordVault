"""Build a small deployment archive using an explicit source allowlist."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json

root = Path(__file__).resolve().parent.parent
output = root.parent / 'pythonanywhere-upload'
output.mkdir(exist_ok=True)
archive = output / 'password-vault-pythonanywhere.zip'
folders = ['accounts', 'api', 'vault', 'password_manager', 'templates', 'static', 'scripts', 'deploy']
files = [root / name for name in ['manage.py', 'requirements.txt', 'requirements.in', 'README.md', 'SETUP.txt', '.env.example', '.gitignore']]
for folder in folders:
    files.extend(path for path in (root / folder).rglob('*') if path.is_file())
files = sorted({path for path in files
                if not any(part in {'__pycache__', '.DS_Store', 'node_modules', '.venv'} for part in path.parts)
                and path.suffix not in {'.pyc', '.sqlite3'}
                and not (path.parent == root / 'deploy' and path.suffix != '.py' and path.name != 'PYTHONANYWHERE.txt')
                and path.name not in {'.env', 'wsgi.generated.py'}})
with ZipFile(archive, 'w', ZIP_DEFLATED) as bundle:
    for path in files:
        bundle.write(path, 'password-vault/' + path.relative_to(root).as_posix())
with ZipFile(archive) as bundle:
    names = bundle.namelist()
    assert all('/.env' not in name or name.endswith('/.env.example') for name in names)
    assert all('.sqlite3' not in name and '/.venv/' not in name for name in names)
    assert bundle.testzip() is None
metadata = {
    'archive': archive.name,
    'files': len(names),
    'size_bytes': archive.stat().st_size,
    'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'includes_secrets': False,
    'includes_local_database': False,
}
(output / 'package-manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata, indent=2))
print(archive)
