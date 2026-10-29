#!/usr/bin/env python3
"""Деплой pipeline/ в $HERMES_HOME/scripts/ + проверка расхождений.

Зачем отдельный шаг вместо симлинков: cron lifecycle_guard резолвит путь скрипта
и блокирует всё, что уходит за пределы ~/.hermes/scripts. Симлинк на файл внутри
plugins/ резолвится наружу и падает с "script path resolves outside the scripts
directory" — проверено на живых джобах d79bd2e1 и c03a2789.

Поэтому канон живёт в репозитории (pipeline/), а сюда копируется. --check ничего
не пишет и возвращает 1, если deployed-файлы разошлись с каноном.

Использование:
    python pipeline/deploy.py            # скопировать все скрипты
    python pipeline/deploy.py --check    # только проверить расхождения
"""

import argparse
import filecmp
import hashlib
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = ["vault_vector_index.py", "auto-capture-obsidian.py", "daily-note.py",
           "daily-note-fallback.py", "obsidian-weekly-review.py",
           "backfill-knowledge-tags.py", "memory_daily_stats.py"]


def dest_dir() -> Path:
    home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    return home / "scripts"


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="только проверить, ничего не писать")
    args = ap.parse_args()

    target = dest_dir()
    target.mkdir(parents=True, exist_ok=True)
    drift, copied = [], []

    for name in SCRIPTS:
        src = HERE / name
        if not src.exists():
            print(f"MISSING  {name} (нет в pipeline/)")
            drift.append(name)
            continue
        dst = target / name

        if dst.is_symlink():
            print(f"SYMLINK  {name} -> {dst.resolve()}  (сломает cron, будет заменён файлом)")
            dst.unlink()

        if dst.exists() and filecmp.cmp(src, dst, shallow=False):
            print(f"same     {name}  {_digest(src)}")
            continue

        if args.check:
            print(f"DRIFT    {name}  repo={_digest(src)} deployed={_digest(dst) if dst.exists() else 'absent'}")
            drift.append(name)
        else:
            # бэкап ПЕРЕД перезаписью — всегда, а не раз в сутки. 08.10.26: копия
            # «не чаще раза в сутки» замораживала .prev на старом содержимом, и
            # незакоммиченный дрейф терялся безвозвратно (пострадал f14b605ee14e).
            # Ротация .prev -> .prev2 держит две последние версии deployed-файла.
            if dst.exists():
                bak = target / f".{name}.prev"
                if bak.exists():
                    shutil.copy2(bak, target / f".{name}.prev2")
                shutil.copy2(dst, bak)
            shutil.copy2(src, dst)
            copied.append(name)
            print(f"deployed {name}  {_digest(src)}")

    if args.check:
        if drift:
            print(f"\n{len(drift)} расхождений: {' '.join(drift)}")
            print("починить:  python pipeline/deploy.py")
            return 1
        print("\nвсё совпадает")
        return 0

    if copied:
        print(f"\nобновлено: {len(copied)} ({' '.join(copied)})")
    else:
        print("\nничего не менялось")
    return 0


if __name__ == "__main__":
    sys.exit(main())