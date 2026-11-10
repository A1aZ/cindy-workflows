"""Compare the actual Windows/Linux release artifacts, including ZIP metadata."""
import hashlib
from pathlib import Path
import sys

archives = sorted(Path(sys.argv[1]).rglob('sausage-man-monitor.zip'))
if len(archives) != 2:
    raise SystemExit('Expected both Windows and Linux build artifacts.')
hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in archives}
if len(hashes) != 1:
    raise SystemExit('Cross-platform Skill archives differ.')
print('Cross-platform package SHA256:', next(iter(hashes)))
