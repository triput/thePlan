"""One bounded local-file readiness wait, not a connection/restart retry."""
from pathlib import Path
from time import monotonic, sleep


if __name__ == '__main__':
    end = monotonic() + 15
    while monotonic() < end:
        path = Path('/fixture-tls/gates.ready')
        if path.exists():
            if path.read_text() != 'READY\n':
                raise RuntimeError('gate readiness mismatch')
            print('READY')
            break
        sleep(.05)
    else:
        raise TimeoutError('gate readiness deadline')
