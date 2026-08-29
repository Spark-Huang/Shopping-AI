#!/usr/bin/env python3
"""Assert en/zh i18n resources have identical key sets (flat dotted paths)."""

import json
import sys
from pathlib import Path


def flat_keys(obj: dict, prefix: str = "") -> set:
    keys: set = set()
    for k, v in obj.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= flat_keys(v, path)
        else:
            keys.add(path)
    return keys


def main() -> int:
    base = Path(__file__).resolve().parent.parent / "src" / "i18n"
    en = json.loads((base / "en.json").read_text(encoding="utf-8"))
    zh = json.loads((base / "zh.json").read_text(encoding="utf-8"))
    en_keys, zh_keys = flat_keys(en), flat_keys(zh)
    missing_in_zh = sorted(en_keys - zh_keys)
    missing_in_en = sorted(zh_keys - en_keys)
    if missing_in_zh or missing_in_en:
        for k in missing_in_zh:
            print(f"MISSING in zh.json: {k}")
        for k in missing_in_en:
            print(f"MISSING in en.json: {k}")
        return 1
    # Also catch empty values (strings, lists, or nested containers)
    for name, res in (("en", en), ("zh", zh)):
        for k in flat_keys(res):
            node = res
            for part in k.split("."):
                node = node[part]
            if isinstance(node, str):
                empty = not node.strip()
            elif isinstance(node, list):
                empty = not node or any(
                    isinstance(v, str) and not v.strip() for v in node
                )
            else:
                empty = False
            if empty:
                print(f"EMPTY value in {name}.json: {k}")
                return 1
    print(f"OK: {len(en_keys)} keys identical in en.json and zh.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
