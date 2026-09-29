#!/usr/bin/env python3
"""Доводит Cargo.lock до состояния, которое читает cargo 1.55.

Идём от ошибки старого cargo: он сам называет крейт, чей манифест не смог
прочитать или чью версию не смог подобрать. Откатываем его СОВРЕМЕННЫМ cargo
(старый не может - для отката ему надо прочитать тот самый манифест),
возвращаем формат lock к версии 3 и повторяем.
"""
import json, pathlib, re, subprocess, urllib.request

CUTOFF = "2021-10-01"
TC = "nightly-2021-08-01"
DIR = pathlib.Path.home() / "Projects/holt/research/probes/flipper"
LOCK = DIR / "Cargo.lock"

def vt(s): return tuple(int(x) for x in re.findall(r"\d+", s)[:3]) or (0,)

def compat(a, b):
    if a[0] != b[0]: return False
    if a[0] == 0 and len(a) > 1 and len(b) > 1 and a[1] != b[1]: return False
    return True

# Ручные подпорки: crates.io отдаёт только последние ~44 версии и отклоняет
# per_page (400), поэтому для крейтов с длинной историей автоподбор слеп.
MANUAL = {
    "crossbeam-utils": "0.8.5", "crossbeam-epoch": "0.9.5",
    "crossbeam-channel": "0.5.1", "crossbeam-deque": "0.8.1",
    "libc": "0.2.103", "once_cell": "1.8.0", "itoa": "0.4.8",
    "ryu": "1.0.5", "serde_json": "1.0.68", "thiserror": "1.0.29",
    "thiserror-impl": "1.0.29", "unicode-width": "0.1.9",
    "winapi-util": "0.1.5", "ppv-lite86": "0.2.10", "csv": "1.1.6",
    "rayon": "1.5.1", "rayon-core": "1.9.1", "js-sys": "0.3.55",
    "web-sys": "0.3.55", "wasm-bindgen": "0.2.78",
    "wasm-bindgen-macro": "0.2.78", "wasm-bindgen-macro-support": "0.2.78",
    "wasm-bindgen-shared": "0.2.78", "wasm-bindgen-backend": "0.2.78",
    "bumpalo": "3.7.1", "either": "1.6.1", "impl-trait-for-tuples": "0.2.1",
}

def target(crate, cur):
    if crate in MANUAL and MANUAL[crate] != cur:
        return MANUAL[crate]
    # ВАЖНО: без per_page crates.io отдаёт только последние ~44 версии,
    # и старые релизы просто не видны - подбор молча решает, что их нет.
    vs = []
    try:
        for page in range(1, 8):
            url = (f"https://crates.io/api/v1/crates/{crate}/versions"
                   f"?per_page=100&page={page}")
            req = urllib.request.Request(url, headers={"user-agent": "holt-research"})
            with urllib.request.urlopen(req, timeout=25) as r:
                chunk = json.load(r)["versions"]
            vs += chunk
            if len(chunk) < 100: break
    except Exception:
        if not vs: return None
    ok = [v for v in vs if not v.get("yanked")
          and not re.search(r"[-+](alpha|beta|rc|pre)", v["num"])
          and v["created_at"][:10] < CUTOFF and compat(vt(v["num"]), vt(cur))]
    if not ok: return None
    ok.sort(key=lambda v: vt(v["num"]))
    return ok[-1]["num"]

def lock_v3():
    s = LOCK.read_text()
    s2 = re.sub(r'^version = 4$', 'version = 3', s, count=1, flags=re.M)
    if s2 != s: LOCK.write_text(s2)

for i in range(1, 41):
    lock_v3()
    r = subprocess.run(["cargo", f"+{TC}", "metadata", "--format-version", "1"],
                       cwd=DIR, capture_output=True, text=True)
    if r.returncode == 0:
        print(f"дерево сошлось на шаге {i}"); raise SystemExit(0)
    err = r.stderr
    m = (re.search(r"failed to parse manifest at `.*/([a-zA-Z0-9_.-]+)-(\d+\.\d+\.\d+)/Cargo\.toml`", err)
         or re.search(r"failed to select a version for the requirement `([a-zA-Z0-9_-]+) = \"=?(\d+\.\d+\.\d+)\"", err)
         or re.search(r"failed to download `([a-zA-Z0-9_-]+) v(\d+\.\d+\.\d+)`", err))
    if not m:
        print("не понял ошибку:"); print("\n".join(err.splitlines()[:6])); raise SystemExit(1)
    crate, cur = m.group(1), m.group(2)
    tgt = target(crate, cur)
    if not tgt or tgt == cur:
        print(f"{crate} {cur}: нет подходящей версии"); raise SystemExit(1)
    u = subprocess.run(["cargo", "update", "-p", f"{crate}@{cur}", "--precise", tgt],
                       cwd=DIR, capture_output=True, text=True)
    status = "ок" if u.returncode == 0 else "не удалось"
    print(f"  {crate}: {cur} -> {tgt}  {status}", flush=True)
    if u.returncode != 0:
        print("   ", (u.stderr or "").strip().splitlines()[:2]); raise SystemExit(1)
print("исчерпал шаги"); raise SystemExit(1)
