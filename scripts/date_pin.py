#!/usr/bin/env python3
"""Ставит всему дереву версии по состоянию на заданную дату.

Минимальные версии оказались слишком агрессивны: они дают крейты 2015-2019
годов, которые не умеют no_std, конфликтуют lang item'ами и вообще не
рассчитаны на edition 2018. А максимальные тянут edition 2021, которую
cargo 1.55 не читает. Нужно ровно то, что было актуально осенью 2021.
"""
import json, pathlib, re, subprocess, sys, urllib.request

CUTOFF = "2021-10-01"
TC = "nightly-2021-08-01"
DIR = pathlib.Path.home() / "Projects/holt/research/probes/flipper"

def vt(s):
    return tuple(int(x) for x in re.findall(r"\d+", s)[:3]) or (0,)

def compat(a, b):
    """Совместимы ли версии по semver: одинаковый мажор, а для 0.x - минор."""
    if a[0] != b[0]: return False
    if a[0] == 0 and len(a) > 1 and len(b) > 1 and a[1] != b[1]: return False
    return True


def newest_before(crate, cur=None):
    url = f"https://crates.io/api/v1/crates/{crate}/versions"
    req = urllib.request.Request(url, headers={"user-agent": "holt-research"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            vs = json.load(r)["versions"]
    except Exception:
        return None
    ok = [v for v in vs if not v.get("yanked")
          and not re.search(r"[-+](alpha|beta|rc|pre)", v["num"])
          and v["created_at"][:10] < CUTOFF]
    # Оставляем только совместимые с текущей: иначе для crossbeam-deque
    # выбирается 0.7.4 - бэкпорт, изданный ПОЗЖЕ 0.8.1, но не подходящий
    # под требование ^0.8. Сортировать надо по номеру, а не по календарю.
    if cur:
        cv = vt(cur)
        ok = [v for v in ok if compat(vt(v["num"]), cv)]
    if not ok: return None
    ok.sort(key=lambda v: vt(v["num"]))
    return ok[-1]["num"]

lock = (DIR / "Cargo.lock").read_text()
pkgs = re.findall(r'\[\[package\]\]\nname = "([^"]+)"\nversion = "([^"]+)"', lock)
print(f"крейтов в lock: {len(pkgs)}")

bumped = skipped = failed = 0
for name, cur in pkgs:
    if name.startswith("ink_") or name in ("flipper",):
        continue                      # ink прибит намеренно
    tgt = newest_before(name, cur)
    # Важно: ставим версию НА ДАТУ, в любую сторону. Раньше здесь стояла
    # проверка vt(tgt) <= vt(cur), и из-за неё крейты новее отсечки - а это
    # весь пласт edition 2021 - молча пропускались.
    if not tgt or tgt == cur:
        skipped += 1
        continue
    # Правим lock СОВРЕМЕННЫМ cargo: старый (1.55) не может откатить крейт,
    # потому что для этого ему надо прочитать манифест текущей версии, а тот
    # на edition 2021 и не читается. Замкнутый круг. Сборку по готовому lock
    # старый cargo уже осилит.
    r = subprocess.run(["cargo", "update", "-p", f"{name}@{cur}",
                        "--precise", tgt], cwd=DIR, capture_output=True, text=True)
    if r.returncode == 0:
        print(f"  {name}: {cur} -> {tgt}", flush=True); bumped += 1
    else:
        failed += 1
print(f"\nподнято: {bumped}, пропущено: {skipped}, не удалось: {failed}")
