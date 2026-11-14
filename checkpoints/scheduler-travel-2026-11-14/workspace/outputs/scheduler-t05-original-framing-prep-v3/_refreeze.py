import json, hashlib, shutil
from pathlib import Path
FR = Path(__file__).resolve().parent
V = FR / "packet/fake-only-t05-framing-verification"
NA = FR.parent / "scheduler-t05-native-provenance-prep-v3/native-provenance"

def H(p):
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()

pins = [{"relative_path": p.relative_to(FR / "packet").as_posix(), "sha256": H(p)} for p in sorted((FR / "packet").rglob("*")) if p.is_file()]
adm = json.loads((FR / "VERIFICATION-ADMISSION.json").read_text(encoding="utf-8"))
adm["packet_files"] = pins
adm["packet_file_pin_count"] = len(pins)
(FR / "VERIFICATION-ADMISSION.json").write_text(json.dumps(adm, indent=2) + "\n", encoding="utf-8", newline="\n")
adm_sha = H(FR / "VERIFICATION-ADMISSION.json")
(FR / "Commands.ps1.txt").write_text(
    "& '" + str(FR / "Invoke-Verification.ps1") + "' -AdmissionSHA256 '" + adm_sha + "'\n",
    encoding="utf-8",
    newline="\n",
)
sums = ["admit_outer.py", "invoke_t05_fake.py", "check_t05_framing_original.py", "EXPECTED-ORIGINAL.json", "INPUT-MANIFEST.json", "REVIEW.md"]
(V / "PACKET-SHA256SUMS.txt").write_text("\n".join(f"{H(V/n)}  {n}" for n in sums) + "\n", encoding="utf-8", newline="\n")
exes = {
    "check_t05_framing_original.py": H(V / "check_t05_framing_original.py"),
    "invoke_t05_fake.py": H(V / "invoke_t05_fake.py"),
    "admit_outer.py": H(V / "admit_outer.py"),
    "Invoke-Verification.ps1": H(FR / "Invoke-Verification.ps1"),
    "collect-parser-sources.sh": H(NA / "collect-parser-sources.sh"),
    "verify_native_provenance.py": H(NA / "verify_native_provenance.py"),
}
tip = json.loads((FR / "TIP-FREEZE.json").read_text(encoding="utf-8"))
tip["admission_sha256"] = adm_sha
tip["executables"] = exes
(FR / "TIP-FREEZE.json").write_text(json.dumps(tip, indent=2) + "\n", encoding="utf-8", newline="\n")
tip_sha = H(FR / "TIP-FREEZE.json")
(FR / "ARTIFACT-HASHES.txt").write_text(f"TIP-FREEZE.json sha256: {tip_sha}\nVERIFICATION-ADMISSION.json sha256: {adm_sha}\n", encoding="utf-8", newline="\n")
drop = Path(r"F:\DropFolder\pending\post-native-t05-source-fake-prep-jim-v3-2026-11-11")
for n in ("TIP-FREEZE.json", "ARTIFACT-HASHES.txt", "Commands.ps1.txt", "VERIFICATION-ADMISSION.json"):
    shutil.copy2(FR / n, drop / n)
print(tip_sha, adm_sha, exes["check_t05_framing_original.py"], exes["verify_native_provenance.py"], exes["collect-parser-sources.sh"])
