"""One bounded local-read readiness command. No database connection attempts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    end = time.monotonic() + 20
    root = Path('/fixture-tls')
    while time.monotonic() < end:
        log = root / 'server.log'
        if log.exists():
            if log.stat().st_size > 262144:
                raise RuntimeError('bootstrap log cap')
            data = log.read_bytes()
            if b'FATAL:' in data or b'PANIC:' in data:
                raise RuntimeError('database startup failed')
            if b'database system is ready to accept connections' in data:
                break
        time.sleep(.05)
    else:
        raise TimeoutError('database readiness deadline')
    def version(argv):
        result = subprocess.run(argv, capture_output=True, check=True,
                                timeout=max(.01, end-time.monotonic()))
        if result.stderr or len(result.stdout) > 4096:
            raise RuntimeError('version output refused')
        return result.stdout.decode('ascii').strip()
    result = {'ready': True,
        'ca_sha256': hashlib.sha256((root/'ca.crt').read_bytes()).hexdigest().upper(),
        'runtime_pins': {'python': list(sys.version_info[:3]),
                         'postgres': version(['postgres', '--version']),
                         'openssl': version(['openssl', 'version'])}}
    if time.monotonic() >= end:
        raise TimeoutError('readiness evidence deadline')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
