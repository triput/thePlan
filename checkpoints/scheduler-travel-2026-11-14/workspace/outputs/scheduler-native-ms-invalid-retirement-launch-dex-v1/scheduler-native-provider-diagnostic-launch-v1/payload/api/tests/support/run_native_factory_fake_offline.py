"""Held fake-only entry. No installation, native checkout, or endpoint binding."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def deny_external_effects(event, args):
    if event.startswith("socket.") or event in {
        "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn",
    }:
        raise RuntimeError("fake-only factory verification: external effect refused")


def main():
    sys.dont_write_bytecode = True
    sys.addaudithook(deny_external_effects)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_CURRENT_TEST"):
        os.environ.pop(name, None)
    sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
    from support.run_covering_refresh_http_harness_offline import install_offline_guards
    install_offline_guards()
    # libpq bypasses Python socket hooks. Refuse its application checkout seam.
    from app.services import covering_native_checkout
    def refused(*args, **kwargs):
        raise RuntimeError("fake-only factory verification: native checkout refused")
    covering_native_checkout.checkout_postgresql = refused
    import pytest
    return int(pytest.main([
        "-c", str(ROOT / "tests/support/_empty_pytest.ini"),
        "--noconftest", "-p", "no:cacheprovider", "-x", "-q", "--tb=short",
        str(ROOT / "tests/test_covering_native_orm_factory.py"),
    ]))


if __name__ == "__main__":
    raise SystemExit(main())
