"""Initialize a mounted data directory, then drop all root credentials before service startup."""
import os
from pathlib import Path
import sys

def main():
    directory = Path(os.getenv("DATA_DIR", "/var/lib/jarvis"))
    if not directory.is_absolute() or str(directory) in ("/", "/etc", "/app", "/usr", "/var"):
        raise SystemExit("DATA_DIR must be a dedicated absolute directory")
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink():
        raise SystemExit("DATA_DIR may not be a symlink")
    if os.geteuid() == 0:
        os.chown(directory, 10001, 10001)
        os.chmod(directory, 0o700)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    os.umask(0o077)
    os.execvp(sys.argv[1], sys.argv[1:])

if __name__ == "__main__":
    main()
