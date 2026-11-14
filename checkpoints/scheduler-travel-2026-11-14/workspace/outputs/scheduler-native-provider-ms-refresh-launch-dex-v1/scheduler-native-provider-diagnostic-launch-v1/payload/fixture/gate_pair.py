"""DB-side joined gate process; stdout contains only its completion receipt."""
import json
import os
from pathlib import Path
import sys
from threading import Event, Thread, Timer
from time import monotonic

# Explicit fixture-only import under -I -S; no application imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_service import serve_case


def main(seconds):
    if not 1 <= seconds <= 900:
        raise ValueError('gate pair deadline')
    root = Path('/fixture-tls')
    end = monotonic() + seconds
    watchdog = Timer(seconds + 2, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    errors = []
    threads = []
    readiness = []
    def run(case, terminal, ready):
        try:
            serve_case(case_id=case, terminal=terminal, seconds=min(seconds, 240), ready=ready)
        except BaseException as exc:
            errors.append(type(exc).__name__)
    try:
        for case, terminal in (('N06', b'COMMIT'), ('N07', b'ROLLBACK')):
            ready = Event()
            thread = Thread(target=run, args=(case, terminal, ready))
            thread.start()
            threads.append(thread)
            readiness.append(ready)
        for ready in readiness:
            if not ready.wait(max(0, min(10, end-monotonic()))):
                raise RuntimeError('gate readiness failed')
        with (root/'gates.ready').open('x') as handle:
            handle.write('READY\n')
        for thread in threads:
            thread.join(max(0, end-monotonic()))
        if any(t.is_alive() for t in threads) or errors:
            raise RuntimeError('gate pair failure')
        receipts = [json.loads((root/(case+'.result.json')).read_text()) for case in ('N06', 'N07')]
        for receipt, tag in zip(receipts, ('COMMIT', 'ROLLBACK')):
            if (receipt.get('complete') is not True or receipt.get('backend_tag') != tag
                    or receipt.get('backend_idle') is not True
                    or receipt.get('terminal_response_bytes_forwarded') != 0):
                raise RuntimeError('gate evidence mismatch')
        print(json.dumps({'joined': True, 'receipts': receipts}, sort_keys=True))
    finally:
        # Failure retains the hard watchdog until all gate workers have ended.
        if all(not t.is_alive() for t in threads):
            watchdog.cancel()
            watchdog.join(1)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('explicit gate deadline required')
    main(int(sys.argv[1]))
