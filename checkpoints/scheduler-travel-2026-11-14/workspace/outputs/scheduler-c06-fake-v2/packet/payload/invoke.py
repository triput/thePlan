"""Prepared host invocation; an incomplete/held launch config always refuses."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    path = root/'launch-config.json'
    if hashlib.sha256(path.read_bytes()).hexdigest().upper() != args.config_sha256:
        raise RuntimeError('launch config mismatch')
    config = json.loads(path.read_text())
    if config.get('launch_ready') is not True:
        raise RuntimeError('HELD: launch configuration incomplete/unreviewed')
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError('require isolated no-site no-bytecode interpreter')
    sys.path.insert(0, str(root/'fixture'))
    from supervisor import Plan, run_once
    from docker_transport import DockerOps
    plan = Plan(packet=config['packet'], manifest_sha256=args.manifest_sha256,
        case_ids=tuple(config['case_ids']), expected_unknown_cases=tuple(config['expected_unknown_cases']),
        suite_seconds=config['suite_seconds'])
    output = Path(config['receipt_directory'])
    # Fresh exclusive attempt directory; no output inside immutable source tree.
    if output.resolve().is_relative_to(root):
        raise RuntimeError('receipt directory overlaps source tree')
    output.mkdir(parents=False, exist_ok=False)
    public = output/'public-ca'
    public.mkdir()
    config['public_ca_directory'] = str(public)
    config['source_directory'] = str(root)
    config['manifest'] = str(root/'SHA256SUMS.txt')
    # Config must have frozen the exact future output directory/mount declaration.
    with (output/'commands.jsonl').open('x', encoding='utf-8') as commands:
        def record(event, data):
            commands.write(json.dumps({'event': event, 'data': data}, sort_keys=True)+'\n')
            commands.flush()
        ops = DockerOps(config, record)
        run_once(plan, ops, output/'receipt.jsonl')


if __name__ == '__main__':
    main()
