"""HELD: exact HTTPS port admission, extracted class and host urlsplit.
No application/vendor imports, sockets or transport. Preparation is not PASS.
Only a separately approved invocation may parse/compile/exercise this source.
"""
from __future__ import annotations
import ast
import dataclasses
import hashlib
import ipaddress
import json
import sys
import types
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULT = HERE / "FAKE-PORT-RESULT.json"
POLICY = "app/services/covering_transport_policy.py"
OLD = b"and (u.port or 443)==self.port and not u.username"
NEW = b"and (443 if u.port is None else u.port)==self.port and not u.username"
IDS = (
    "PORT-443-ABSENT", "PORT-443-EXPLICIT", "PORT-443-ZERO", "PORT-443-OTHER",
    "PORT-8443-ABSENT", "PORT-8443-EXPLICIT", "PORT-8443-ZERO",
    "PORT-SOURCE-INVENTORY", "PORT-BAD-PIN",
)

class Refused(Exception):
    pass

def verify_sources(rows):
    seen = set()
    for row in rows:
        rel = row["relative_path"]
        path = (ROOT / rel).resolve()
        if not path.is_relative_to(ROOT) or rel in seen:
            raise ValueError("source inventory path")
        seen.add(rel)
        raw = path.read_bytes()
        if len(raw) != row["size"] or hashlib.sha256(raw).hexdigest().upper() != row["sha256"]:
            raise ValueError("source pin mismatch")
    actual = {p.relative_to(ROOT).as_posix() for v in ("original", "candidate")
              for p in (ROOT / v).rglob("*") if p.is_file()}
    if seen != actual or len(seen) != 468:
        raise ValueError("source inventory mismatch")

def build(version):
    path = ROOT / version / POLICY
    text = path.read_bytes().decode("utf-8")
    if "\r" in text.replace("\r\n", ""):
        raise ValueError("bare CR source")
    tree = ast.parse(text, filename=str(path))
    picked = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HTTPSPeer"]
    if len(picked) != 1:
        raise ValueError("class extraction inventory")
    name = "port_fixture_" + version
    module = types.ModuleType(name)
    sys.modules[name] = module
    env = module.__dict__
    env.update(dataclass=dataclasses.dataclass, ip_address=ipaddress.ip_address,
               urlsplit=urllib.parse.urlsplit, CoveringTransportRefused=Refused)
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    code = ast.fix_missing_locations(ast.Module(body=[future] + picked, type_ignores=[]))
    exec(compile(code, str(path), "exec"), env)
    return env["HTTPSPeer"]

def outcome(peer_class, port, url):
    peer = peer_class(hostname="graph.example.test", address="127.0.0.1",
                      port=port, ca_file="FAKE-CA-NOT-OPENED")
    try:
        parsed = peer.check_url(url)
    except Refused:
        return {"outcome": "REFUSED"}
    return {"outcome": "ACCEPTED", "parsed_port": parsed.port,
            "configured_port": peer.port}

def inventory_control(rows):
    changed = []
    for row in rows:
        rel = row["relative_path"]
        if not rel.startswith("original/"):
            continue
        local = rel[len("original/"):]
        left = (ROOT / "original" / local).read_bytes()
        right = (ROOT / "candidate" / local).read_bytes()
        if left != right:
            changed.append(local)
            if local != POLICY or left.count(OLD) != 1 or left.replace(OLD, NEW) != right:
                raise AssertionError("unapproved source difference")
    if changed != [POLICY]:
        raise AssertionError("one-file diff inventory")
    return {"changed_files": changed, "source_count": len(rows), "one_expression_only": True}

def main():
    if RESULT.exists():
        raise ValueError("preexisting result")
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):
        raise ValueError("isolation")
    manifest = json.loads((HERE / "INPUT-MANIFEST.json").read_bytes())
    expected = json.loads((HERE / "EXPECTED.json").read_bytes())
    if expected["wire_ids_in_order"] != list(IDS) or list(expected["inputs"]) != list(IDS):
        raise ValueError("control inventory")
    verify_sources(manifest["sources"])
    classes = {v: build(v) for v in ("original", "candidate")}
    observations = {}
    for cid in IDS:
        spec = expected["inputs"][cid]
        if cid == "PORT-SOURCE-INVENTORY":
            observed = inventory_control(manifest["sources"])
        elif cid == "PORT-BAD-PIN":
            bad = [dict(row) for row in manifest["sources"]]
            bad[0]["sha256"] = "0" * 64
            try:
                verify_sources(bad)
            except ValueError as exc:
                if str(exc) != "source pin mismatch":
                    raise
                observed = {"bad_pin_rejected": True}
            else:
                raise AssertionError("corrupt pin admitted")
        else:
            observed = {v: outcome(classes[v], spec["peer_port"], spec["url"])
                        for v in ("original", "candidate")}
        if json.dumps(observed, sort_keys=True) != json.dumps(spec["observation"], sort_keys=True):
            raise AssertionError("control mismatch:" + cid)
        observations[cid] = {"observed_outcome": "PASS", "observation": observed}
    verify_sources(manifest["sources"])
    payload = {"status": "PASS", "class": "FAKE-PORT", "executed": True,
               "source_hashes_verified": True, "inventory_error": None,
               "wire_ids_in_order": list(observations), "inputs": observations,
               "limits": "source-extracted origin validator only; no dial/TLS/native proof"}
    raw = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    if len(raw) > 262144:
        raise ValueError("result cap")
    with RESULT.open("xb") as stream:
        stream.write(raw)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
