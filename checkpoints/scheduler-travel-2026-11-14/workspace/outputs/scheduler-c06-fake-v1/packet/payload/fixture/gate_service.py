"""DB-container one-shot gate process; explicit supervisor start only.

Writes only readiness/result metadata to DB tmpfs, never keys or SQL. It accepts
one loopback client, then exits. There is no retry, background self-launch or CLI
default. Supervisor must join/inspect completion before accepting suite evidence.
"""
import json
from pathlib import Path
import socket
import ssl
from threading import Event
from time import monotonic

from tls_ack_gate import serve_one


def serve_case(*, case_id, terminal, seconds, ready=None):
    if (case_id, terminal) not in (('N06', b'COMMIT'), ('N07', b'ROLLBACK')):
        raise ValueError('unreviewed fault case')
    if type(seconds) is not int or not 1 <= seconds <= 240:
        raise ValueError('explicit bounded gate deadline required')
    root = Path('/fixture-tls')
    end = monotonic() + seconds
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.minimum_version = ssl.TLSVersion.TLSv1_2
    server.load_cert_chain(root/'server.crt', root/'server.key')
    backend = ssl.create_default_context(cafile=str(root/'ca.crt'))
    backend.minimum_version = ssl.TLSVersion.TLSv1_2
    armed = Event()
    # Setup traffic is unfaulted; serve_one arms after the exact marker succeeds.
    evidence = {'case_id': case_id, 'complete': False}
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 15432 if case_id == 'N06' else 15433))
        listener.listen(1)
        listener.settimeout(max(.001, end-monotonic()))
        with (root/(case_id+'.ready')).open('x', encoding='ascii') as handle:
            handle.write('READY\n')
        if ready is not None:
            ready.set()
        try:
            client, _ = listener.accept()
            with client:
                serve_one(client, server_context=server, backend_context=backend,
                    backend_port=5432, deadline=end, terminal=terminal,
                    armed=armed, receipt=evidence)
            evidence['complete'] = True
        except BaseException as error:
            evidence['failure_type'] = type(error).__name__
            raise
        finally:
            with (root/(case_id+'.result.json')).open('x', encoding='ascii') as handle:
                json.dump(evidence, handle, sort_keys=True)
