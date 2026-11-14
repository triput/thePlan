"""Prepared Docker Ops binding. Never invoked on import; no default config.

Config is a separately hash-reviewed launch input, not discovered live. It pins
images, executable, exact argv/entrypoints, users, mounts and inspect projections.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import ssl
import subprocess
import threading
from time import monotonic


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


class DockerOps:
    def __init__(self, config, record):
        self.c = config
        self._record_lock = threading.Lock()
        def synchronized_record(event, data):
            with self._record_lock:
                record(event, data)
        self.record = synchronized_record
        self.ids = {}
        self.calls = 0
        self.ca_hash = None
        self.untrusted_ca_hash = None
        self.ca_path = Path(config['public_ca_directory']) / 'ca.crt'
        if not Path(config['docker']).is_absolute():
            raise ValueError('absolute Docker executable required')
        if config['endpoint'] != 'npipe:////./pipe/dockerDesktopLinuxEngine':
            raise ValueError('unreviewed Docker endpoint')
        if any(k.startswith('DOCKER_') for k in os.environ):
            raise ValueError('ambient Docker settings refused')
        mandatory = {'Privileged': False, 'ReadonlyRootfs': True,
            'PublishAllPorts': False, 'PortBindings': {}, 'CapAdd': None,
            'Devices': [], 'DeviceRequests': None, 'Memory': 1073741824,
            'MemorySwap': 1073741824, 'NanoCpus': 1000000000, 'PidsLimit': 64,
            'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],
            'RestartPolicy': {'Name': 'no', 'MaximumRetryCount': 0}}
        for role in ('database', 'runner'):
            projection = config['roles'][role]['host_config_projection']
            if any(projection.get(k) != v for k, v in mandatory.items()):
                raise ValueError('incomplete or unsafe isolation projection')
        if [str(self.ca_path.parent), '/public-ca'] not in config['roles']['runner']['readonly_binds']:
            raise ValueError('runner public CA read-only mount required')

    def _record_runner_stop(self, args, stderr, returncode):
        """Retain only validated metadata for this owned runner's attach failure."""
        runner = self.ids.get('runner')
        if not runner or args != ['start', '--attach', runner]:
            return
        try:
            self._id(runner)
            if type(returncode) is not int or not -2147483648 <= returncode <= 4294967295:
                raise ValueError('exit code')
            data = bytes(stderr)
            if not data or len(data) > 4096 or not data.endswith(b'\n') or data.count(b'\n') != 1 or b'\r' in data:
                raise ValueError('envelope size')
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError('duplicate key')
                    result[key] = value
                return result
            def identifier(value):
                if type(value) is not str or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', value):
                    raise ValueError('kind')
                return value
            value = json.loads(data.decode('utf-8'), object_pairs_hook=pairs)
            if type(value) is not dict or set(value) not in ({'status', 'kind'}, {'status', 'kind', 'diagnostic'}) or value['status'] != 'STOP':
                raise ValueError('schema')
            safe = {'status': 'STOP', 'kind': identifier(value['kind']), 'cli_exit_code': returncode}
            if 'diagnostic' in value:
                diagnostic = value['diagnostic']
                if type(diagnostic) is not dict or set(diagnostic) != {'version', 'exceptions', 'truncated'}:
                    raise ValueError('diagnostic schema')
                if type(diagnostic['version']) is not int or diagnostic['version'] != 1 or type(diagnostic['truncated']) is not bool:
                    raise ValueError('diagnostic version')
                entries = diagnostic['exceptions']
                if type(entries) is not list or not 1 <= len(entries) <= 3:
                    raise ValueError('exception bound')
                root = Path(self.c['source_directory']).resolve()
                owned = {}
                for row in Path(self.c['manifest']).read_text().splitlines():
                    pin, rel = row.split('  ', 1)
                    if re.fullmatch(r'[A-F0-9]{64}', pin):
                        owned[rel] = pin
                accepted = []
                for entry in entries:
                    if type(entry) is not dict or set(entry) != {'kind', 'frames'}:
                        raise ValueError('exception schema')
                    name = identifier(entry['kind'])
                    if type(entry['frames']) is not list or len(entry['frames']) > 8:
                        raise ValueError('frame bound')
                    frames = []
                    for frame in entry['frames']:
                        if type(frame) is not dict or set(frame) != {'path', 'line'}:
                            raise ValueError('frame schema')
                        rel, line = frame['path'], frame['line']
                        if type(rel) is not str or not re.fullmatch(r'[A-Za-z0-9_./-]{1,240}', rel) or not rel.endswith('.py') or rel not in owned:
                            raise ValueError('frame path')
                        path = (root/rel).resolve()
                        if not path.is_relative_to(root) or path.relative_to(root).as_posix() != rel:
                            raise ValueError('frame boundary')
                        content = path.read_bytes()
                        if digest(path) != owned[rel] or type(line) is not int or not 1 <= line <= len(content.splitlines()):
                            raise ValueError('frame source')
                        frames.append({'path': rel, 'line': line})
                    accepted.append({'kind': name, 'frames': frames})
                if accepted[0]['kind'] != safe['kind']:
                    raise ValueError('primary kind')
                safe['diagnostic'] = {'version': 1, 'exceptions': accepted, 'truncated': diagnostic['truncated']}
            else:
                safe['diagnostic_unavailable'] = True
            self.record('runner_stop', safe)
        except BaseException:
            try:
                self.record('runner_stop_diagnostic_refused', {'code': 'INVALID_OR_UNAVAILABLE_STOP_METADATA'})
            except BaseException:
                pass  # Never replace the original command failure with diagnostics.

    def _cmd(self, args, deadline, cap=30, cancel=None):
        if digest(self.c['docker']) != self.c['docker_sha256']:
            raise RuntimeError('Docker executable changed')
        self.calls += 1
        if self.calls > self.c['command_count_cap']:
            raise RuntimeError('command count cap')
        end = min(deadline, monotonic() + cap)
        if end <= monotonic():
            raise TimeoutError('command deadline')
        spec = [self.c['docker'], '--config', self.c['docker_config'],
                '--host', self.c['endpoint'], *args]
        self.record('docker_command', args)
        proc = subprocess.Popen(spec, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW)
        chunks = queue.Queue(maxsize=64)
        stop = threading.Event()
        def pump(stream, tag):
            try:
                while not stop.is_set():
                    data = stream.read1(4096)
                    while not stop.is_set():
                        try:
                            chunks.put((tag, data), timeout=.05)
                            break
                        except queue.Full:
                            continue
                    if not data:
                        break
            finally:
                stream.close()
        threads = [threading.Thread(target=pump, args=(stream, tag), daemon=True)
                   for stream, tag in ((proc.stdout, 0), (proc.stderr, 1))]
        for thread in threads:
            thread.start()
        output = [bytearray(), bytearray()]
        done = set()
        try:
            while len(done) < 2 or proc.poll() is None:
                if monotonic() >= end or (cancel is not None and cancel.is_set()):
                    raise TimeoutError('Docker outcome UNKNOWN')
                try:
                    tag, data = chunks.get(timeout=min(.05, end-monotonic()))
                except queue.Empty:
                    continue
                if not data:
                    done.add(tag)
                else:
                    output[tag].extend(data)
                    if sum(map(len, output)) > self.c['output_byte_cap']:
                        raise RuntimeError('output cap')
            if proc.returncode != 0 or output[1]:
                self._record_runner_stop(args, output[1], proc.returncode)
                raise RuntimeError('Docker exit/stderr failure')
            for thread in threads:
                thread.join(timeout=max(0, min(1, end-monotonic())))
                if thread.is_alive():
                    raise RuntimeError('output worker not joined')
            return bytes(output[0])
        finally:
            stop.set()
            if proc.poll() is None:
                # Stop only the local CLI, never signal/remove a container here.
                proc.kill()
                self.record('cli_stopped_container_state_unknown', True)
            for thread in threads:
                thread.join(timeout=.2)
            self.record('docker_output', {
                'stdout_sha256': hashlib.sha256(output[0]).hexdigest(),
                'stderr_sha256': hashlib.sha256(output[1]).hexdigest(),
                'bytes': sum(map(len, output)),
                'workers_joined': all(not t.is_alive() for t in threads)})

    def _id(self, identifier):
        if identifier not in self.ids.values() or not re.fullmatch('[a-f0-9]{64}', identifier):
            raise ValueError('unowned exact ID')

    def verify_inputs(self, manifest_sha256, *, deadline):
        root = Path(self.c['source_directory']).resolve()
        manifest = Path(self.c['manifest'])
        if digest(manifest) != manifest_sha256:
            return False
        expected = {}
        for line in manifest.read_text(encoding='utf-8-sig').splitlines():
            match = re.fullmatch(r'([A-F0-9]{64})  (.+)', line)
            if not match:
                return False
            pin, rel = match.groups()
            path = (root / rel).resolve()
            if not path.is_relative_to(root) or rel in expected:
                return False
            expected[rel] = pin
            if digest(path) != pin:
                return False
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
                  if p.is_file() and p.resolve() != manifest.resolve()}
        if actual != {Path(p).as_posix() for p in expected}:
            return False
        if self.ca_hash is not None and digest(self.ca_path) != self.ca_hash:
            return False
        if self.untrusted_ca_hash is not None and digest(self.ca_path.parent/'untrusted-ca.crt') != self.untrusted_ca_hash:
            return False
        return monotonic() < deadline

    def verify_runtime_pins(self, *, deadline):
        if digest(self.c['docker']) != self.c['docker_sha256']:
            return False
        for role in ('database', 'runner'):
            pin = self.c['roles'][role]['image']
            if not re.fullmatch(r'sha256:[a-f0-9]{64}', pin):
                return False
            facts = json.loads(self._cmd(['image', 'inspect', pin], deadline))
            if len(facts) != 1 or facts[0]['Id'] != pin:
                return False
            if facts[0]['Config'].get('Volumes') != self.c['roles'][role]['image_volumes']:
                return False
        return True  # Runner must separately compare full library/tool pins.

    def create(self, role, known_ids, *, deadline):
        spec = self.c['roles'][role]
        network = 'none' if role == 'database' else 'container:' + known_ids['database']
        args = ['create', '--pull=never', '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--restart=no', '--log-driver=none',
            '--no-healthcheck', '--memory=1g', '--memory-swap=1g', '--cpus=1',
            '--pids-limit=64', '--network=' + network, '--user=' + spec['user'],
            '--label=dex.native-validation=' + self.c['packet']]
        for source, destination in spec['readonly_binds']:
            args += ['--mount', 'type=bind,src=' + source + ',dst=' + destination + ',readonly']
        for destination, options in spec['tmpfs'].items():
            args += ['--tmpfs', destination + ':' + options]
        if role == 'runner' and self.ca_hash is None:
            raise RuntimeError('public CA not transferred')
        args += ['--entrypoint=' + spec['entrypoint'], spec['image'], *spec['argv']]
        identifier = self._cmd(args, deadline).decode('ascii').strip()
        if not re.fullmatch('[a-f0-9]{64}', identifier):
            raise RuntimeError('creation ID UNKNOWN')
        self.ids[role] = identifier
        return identifier

    def check_identity(self, identifier, role, *, deadline):
        self._id(identifier)
        facts = json.loads(self._cmd(['container', 'inspect', identifier], deadline))
        if len(facts) != 1:
            raise RuntimeError('inspect cardinality')
        item = facts[0]
        spec = self.c['roles'][role]
        if (item['Id'] != identifier or item['Image'] != spec['image']
                or item['Config']['Labels'].get('dex.native-validation') != self.c['packet']
                or item['Config']['User'] != spec['user']
                or item['Config']['Entrypoint'] != [spec['entrypoint']]
                or item['Config']['Cmd'] != spec['argv']):
            raise RuntimeError('identity mismatch')
        expected = dict(spec['host_config_projection'])
        expected['NetworkMode'] = 'none' if role == 'database' else 'container:' + self.ids['database']
        if any(item['HostConfig'].get(k) != v for k, v in expected.items()):
            raise RuntimeError('isolation mismatch')
        mounts = sorted((m['Type'], m['Destination'], m['RW']) for m in item['Mounts'])
        if mounts != sorted(tuple(m) for m in spec['mount_projection']):
            raise RuntimeError('mount mismatch')
        declarations = item['HostConfig'].get('Mounts') or []
        actual_binds = sorted((m['Source'], m['Target'], m.get('ReadOnly', False))
                              for m in declarations if m['Type'] == 'bind')
        if actual_binds != sorted((source, dest, True) for source, dest in spec['readonly_binds']):
            raise RuntimeError('bind source mismatch')
        if item['HostConfig'].get('Tmpfs', {}) != spec['tmpfs']:
            raise RuntimeError('tmpfs mismatch')
        return {'status': item['State']['Status'], 'exit_code': item['State']['ExitCode']}

    def start_database(self, identifier, *, deadline):
        self._id(identifier)
        return self._cmd(['start', identifier], deadline).decode('ascii').strip()

    def verify_fixture_ready(self, identifier, *, deadline):
        self._id(identifier)
        ready = self._cmd(['exec', identifier, self.c['database_python'], '-I', '-S', '-B',
                          '/packet/fixture/database_ready.py'], deadline)
        state = json.loads(ready)
        if state['ready'] is not True or state['runtime_pins'] != self.c['database_runtime_pins']:
            raise RuntimeError('database readiness/runtime mismatch')
        # Fixed public-only path: never docker cp a directory containing keys.
        pem = self._cmd(['exec', identifier, '/bin/cat', '/fixture-tls/ca.crt'], deadline)
        if len(pem) > 16384 or not re.fullmatch(
                rb'-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\r?\n?', pem):
            raise RuntimeError('single public CA certificate required')
        ssl.PEM_cert_to_DER_cert(pem.decode('ascii'))
        if list(self.ca_path.parent.iterdir()):
            raise RuntimeError('public CA directory must be fresh and empty')
        with self.ca_path.open('xb') as handle:
            handle.write(pem)
            handle.flush()
            os.fsync(handle.fileno())
        self.ca_hash = hashlib.sha256(pem).hexdigest().upper()
        if digest(self.ca_path) != self.ca_hash:
            raise RuntimeError('public CA readback mismatch')
        self.record('public_ca_transferred', {'sha256': self.ca_hash, 'bytes': len(pem)})
        bad_pem = self._cmd(['exec', identifier, '/bin/cat', '/fixture-tls/untrusted-ca.crt'], deadline)
        if len(bad_pem) > 16384 or not re.fullmatch(
                rb'-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\r?\n?', bad_pem):
            raise RuntimeError('single negative-control public CA required')
        ssl.PEM_cert_to_DER_cert(bad_pem.decode('ascii'))
        with (self.ca_path.parent/'untrusted-ca.crt').open('xb') as handle:
            handle.write(bad_pem)
        self.untrusted_ca_hash = hashlib.sha256(bad_pem).hexdigest().upper()
        if self.untrusted_ca_hash == self.ca_hash or digest(self.ca_path.parent/'untrusted-ca.crt') != self.untrusted_ca_hash:
            raise RuntimeError('negative-control CA mismatch')
        self.record('negative_control_public_ca_transferred', {'sha256': self.untrusted_ca_hash})
        return (state['ca_sha256'] == self.ca_hash and state['ready'] is True
                and state['runtime_pins'] == self.c['database_runtime_pins'])

    def run_attached(self, identifier, *, deadline):
        self._id(identifier)
        cancel = threading.Event()
        gate_result = []
        gate_error = []
        def gate_worker():
            try:
                output = self._cmd(['exec', self.ids['database'], self.c['database_python'],
                    '-I', '-S', '-B', '/packet/fixture/gate_pair.py', str(self.c['gate_seconds'])],
                    deadline, cap=self.c['gate_seconds']+5, cancel=cancel)
                gate_result.append(json.loads(output))
            except BaseException as error:
                gate_error.append(type(error).__name__)
        gate = threading.Thread(target=gate_worker, daemon=True)
        gate.start()
        try:
            ready = self._cmd(['exec', self.ids['database'], self.c['database_python'],
                '-I', '-S', '-B', '/packet/fixture/gates_ready.py'], deadline)
            if ready.strip() != b'READY' or gate_error:
                raise RuntimeError('gate launch failed')
            report = json.loads(self._cmd(['start', '--attach', identifier], deadline,
                                          cap=self.c['runner_seconds']))
            gate.join(timeout=max(0, deadline-monotonic()))
            if gate.is_alive() or gate_error or len(gate_result) != 1 or gate_result[0].get('joined') is not True:
                raise RuntimeError('gate process not successfully joined')
            receipts = gate_result[0].get('receipts', [])
            if [r.get('case_id') for r in receipts] != ['N06', 'N07']:
                raise RuntimeError('gate case inventory mismatch')
            for r, tag in zip(receipts, ('COMMIT', 'ROLLBACK')):
                if (r.get('complete') is not True or r.get('backend_tag') != tag
                        or r.get('backend_idle') is not True or r.get('terminal_response_bytes_forwarded') != 0):
                    raise RuntimeError('gate outcome evidence mismatch')
            self.record('joined_gate_evidence', gate_result[0])
        finally:
            # Cancel local CLI only on failure. No DB/gate process kill or retry.
            cancel.set()
            gate.join(timeout=2)
            if gate.is_alive():
                raise RuntimeError('host gate worker not joined; container state UNKNOWN')
        if report['runtime_pins'] != self.c['runner_runtime_pins'] or report['ca_sha256'] != self.ca_hash:
            raise RuntimeError('runner pins/public CA mismatch')
        return report

    def remove_exact(self, identifier, *, deadline):
        self._id(identifier)
        return self._cmd(['container', 'rm', identifier], deadline).decode('ascii').strip()

    def verify_absent(self, identifier, *, deadline):
        self._id(identifier)
        return not self._cmd(['ps', '-a', '--no-trunc', '--filter', 'id=' + identifier,
                              '--format', '{{.ID}}'], deadline).strip()

    def sigint_exact(self, identifier, *, deadline):
        self._id(identifier)
        return self._cmd(['kill', '--signal=SIGINT', identifier], deadline).decode('ascii').strip()

    def wait_exact(self, identifier, *, deadline):
        self._id(identifier)
        result = self._cmd(['wait', identifier], deadline).decode('ascii').strip()
        if result != '0':
            raise RuntimeError('DB exit not zero')
        return 0
