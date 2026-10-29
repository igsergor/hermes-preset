#!/usr/bin/env python3
"""Переименовать файлы vault в Android-совместимые имена и починить ссылки в тексте.

Зачем: Android не создаёт файлы с `? " < > | \ / * :` в имени — плагин синка падает
с FILE_NOT_CREATED. Лечится массовым переименованием + заменой старых имён в заметках.

Использование:
    python3 sanitize_filenames.py [--vault ~/obsidian-vault] [--dry-run]

Печатает JSON-карту переименований (old -> new) и число обновлённых файлов.
Идемпотентен: повторный запуск ничего не делает.
"""
import argparse
import json
import os
import re
import unicodedata

BAD = {"?": " -", '"': "'", "<": "-", ">": "-", "|": "-", "\\": "-", "/": "-", "*": "-", ":": " -"}


def safe(name: str) -> str:
    for ch, rep in BAD.items():
        name = name.replace(ch, rep)
    name = unicodedata.normalize("NFC", name)
    return re.sub(r"\s+", " ", name).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default="~/obsidian-vault")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    base = args.vault

    todo = [
        os.path.join(r, f)
        for r, _d, fs in os.walk(base)
        for f in fs
        if any(c in f for c in BAD)
    ]
    print(f"files to rename: {len(todo)}")

    mapping = {}
    for src in todo:
        d, f = os.path.split(src)
        s = safe(f)
        dst = os.path.join(d, s)
        if s == f:
            continue
        if os.path.exists(dst) and os.path.realpath(dst) != os.path.realpath(src):
            stem, ext = os.path.splitext(s)
            i = 2
            while os.path.exists(os.path.join(d, f"{stem} {i}{ext}")):
                i += 1
            dst = os.path.join(d, f"{stem} {i}{ext}")
        if not args.dry_run:
            os.rename(src, dst)
        mapping[os.path.relpath(src, base)] = os.path.relpath(dst, base)
    print(f"renamed: {len(mapping)}")

    pairs = []
    for old, new in mapping.items():
        o = os.path.splitext(os.path.basename(old))[0]
        n = os.path.splitext(os.path.basename(new))[0]
        if o != n:
            pairs.append((o, n))
    pairs.sort(key=lambda x: -len(x[0]))

    changed = 0
    for root, _d, fs in os.walk(base):
        for f in fs:
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            with open(p, encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
            new_text = text
            for o, n in pairs:
                if o in new_text:
                    new_text = new_text.replace(o, n)
            if new_text != text:
                if not args.dry_run:
                    with open(p, "w", encoding="utf-8") as fh:
                        fh.write(new_text)
                changed += 1
    print(f"content files updated: {changed}")

    left = [f for _r, _d, fs in os.walk(base) for f in fs if any(c in f for c in BAD)]
    print(f"remaining unsafe names: {len(left)}")
    if not args.dry_run:
        print(json.dumps(mapping, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()