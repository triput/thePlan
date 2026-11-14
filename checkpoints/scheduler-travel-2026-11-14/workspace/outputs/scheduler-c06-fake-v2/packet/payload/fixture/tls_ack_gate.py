"""Single-connection PostgreSQL TLS fault gate; prepared, never auto-started.

Both hops verify/serve fixture TLS. Backend fixture authentication must be trust
for the isolated synthetic role. No passwords, SQL or row bodies enter receipts.
Caller owns accepted loopback socket, absolute deadline and joined lifecycle.
"""
import socket
import ssl
import struct
from time import monotonic

SSL_REQUEST = struct.pack('!II', 8, 80877103)
LIMIT = 1024 * 1024
ARM_QUERY = b'SELECT 1 /* dex-arm-lost-ack */\0'
ARM_TOKEN = b'dex-arm-lost-ack'
# SELECT 1: one text int4 column, one scalar row, then in-transaction readiness.
ARM_DESCRIPTION = (struct.pack('!h', 1) + b'?column?\0'
                   + struct.pack('!IhIhih', 0, 0, 23, 4, -1, 0))
ARM_ROW = struct.pack('!hi', 1, 1) + b'1'


def remaining(deadline):
    left = deadline - monotonic()
    if left <= 0:
        raise TimeoutError('fixture gate deadline')
    return left


def read(sock, size, deadline):
    result = bytearray()
    while len(result) < size:
        sock.settimeout(remaining(deadline))
        chunk = sock.recv(size - len(result))
        if not chunk:
            raise RuntimeError('incomplete PostgreSQL frame')
        result.extend(chunk)
    return bytes(result)


def send(sock, data, deadline):
    sock.settimeout(remaining(deadline))
    sock.sendall(data)


def frame(sock, deadline, startup=False):
    kind = b'' if startup else read(sock, 1, deadline)
    header = read(sock, 4, deadline)
    size, = struct.unpack('!I', header)
    if not 4 <= size <= LIMIT:
        raise RuntimeError('frame size refused')
    body = read(sock, size - 4, deadline)
    return kind, body, kind + header + body


def serve_one(raw_client, *, server_context, backend_context, backend_port,
              deadline, terminal, armed, receipt):
    """Withhold only exact simple terminal C/Z after explicit arming.

    An expected fault succeeds only with backend CommandComplete + idle observed,
    zero terminal response bytes forwarded, and the client connection closed.
    Other protocol errors escape. This gate does not authorize a subsequent run.
    """
    if armed.is_set():
        raise ValueError('gate must start unarmed')
    if terminal not in (b'COMMIT', b'ROLLBACK'):
        raise ValueError('unsupported terminal')
    if backend_context.verify_mode != ssl.CERT_REQUIRED or not backend_context.check_hostname:
        raise ValueError('backend verify-full required')
    if raw_client.getpeername()[0] != '127.0.0.1':
        raise ValueError('loopback client required')
    if read(raw_client, 8, deadline) != SSL_REQUEST:
        raise RuntimeError('TLS negotiation required')
    send(raw_client, b'S', deadline)
    raw_client.settimeout(remaining(deadline))
    with server_context.wrap_socket(raw_client, server_side=True) as client:
        with socket.create_connection(('127.0.0.1', backend_port),
                                      timeout=remaining(deadline)) as raw_backend:
            send(raw_backend, SSL_REQUEST, deadline)
            if read(raw_backend, 1, deadline) != b'S':
                raise RuntimeError('backend refused TLS')
            raw_backend.settimeout(remaining(deadline))
            with backend_context.wrap_socket(raw_backend,
                    server_hostname='native-fixture.invalid') as backend:
                _, startup, wire = frame(client, deadline, startup=True)
                if not startup.startswith(struct.pack('!I', 196608)):
                    raise RuntimeError('protocol version refused')
                fields = startup[4:].split(b'\0')
                if fields[-2:] != [b'', b'']:
                    raise RuntimeError('startup termination')
                fields = fields[:-2]
                if len(fields) % 2 or len(set(fields[::2])) != len(fields)//2:
                    raise RuntimeError('startup fields')
                params = dict(zip(fields[::2], fields[1::2]))
                if params.get(b'user') != b'dex_fixture' or params.get(b'database') != b'dex_fixture':
                    raise RuntimeError('fixture identity required')
                send(backend, wire, deadline)
                for _ in range(128):
                    kind, body, wire = frame(backend, deadline)
                    if kind == b'R' and body != b'\0\0\0\0':
                        raise RuntimeError('fixture trust authentication required')
                    if kind not in (b'R', b'S', b'K', b'Z'):
                        raise RuntimeError('startup response refused')
                    send(client, wire, deadline)
                    if kind == b'Z':
                        if body != b'I':
                            raise RuntimeError('startup not idle')
                        break
                else:
                    raise RuntimeError('startup frame ceiling')
                for _ in range(256):
                    fault = False
                    marker = False
                    for _ in range(64):
                        kind, body, wire = frame(client, deadline)
                        if kind not in (b'Q', b'P', b'B', b'D', b'E', b'S', b'C'):
                            raise RuntimeError('frontend protocol refused')
                        if armed.is_set():
                            # No intervening traffic may consume the one-shot fault.
                            if (kind, body) != (b'Q', terminal + b'\0'):
                                raise RuntimeError('armed next terminal mismatch')
                            fault = True
                        elif (kind, body) == (b'Q', ARM_QUERY):
                            marker = True
                        elif ARM_TOKEN in body:
                            raise RuntimeError('marker shape refused')
                        send(backend, wire, deadline)
                        if kind in (b'Q', b'S'):
                            break
                    else:
                        raise RuntimeError('frontend frame ceiling')
                    if marker:
                        # Buffer only the four bounded expected frames. Never arm
                        # on partial/error/idle completion or forward invalid data.
                        wires = []
                        for expected in ((b'T', ARM_DESCRIPTION), (b'D', ARM_ROW),
                                         (b'C', b'SELECT 1\0'), (b'Z', b'T')):
                            kind, body, wire = frame(backend, deadline)
                            if (kind, body) != expected:
                                raise RuntimeError('arm response mismatch')
                            wires.append(wire)
                        for wire in wires:
                            send(client, wire, deadline)
                        armed.set()
                        continue
                    if fault:
                        kind, body, _ = frame(backend, deadline)
                        if (kind, body) != (b'C', terminal + b'\0'):
                            raise RuntimeError('terminal acknowledgment mismatch')
                        kind, body, _ = frame(backend, deadline)
                        if (kind, body) != (b'Z', b'I'):
                            raise RuntimeError('terminal idle mismatch')
                        receipt.update(backend_tag=terminal.decode('ascii'),
                            backend_idle=True, terminal_response_bytes_forwarded=0,
                            fault='acknowledgment_withheld')
                        # Closing TLS without forwarding C/Z produces loss at a
                        # known protocol boundary, not a timer-based race.
                        return
                    for _ in range(4096):
                        kind, body, wire = frame(backend, deadline)
                        send(client, wire, deadline)
                        if kind == b'Z':
                            break
                    else:
                        raise RuntimeError('backend frame ceiling')
                raise RuntimeError('exchange ceiling')
