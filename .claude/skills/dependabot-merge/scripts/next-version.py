#!/usr/bin/env python3
"""次のパッチバージョンを決定する。

gradle.properties の version を読み、パッチを +1 した値と対応するタグ名を出す。
--apply を付けると gradle.properties を書き換える。

判断の余地はないので、この計算を手でやらないこと。手でやると -SNAPSHOT の
取りこぼしやタグの重複に気づかないまま push まで進んでしまう。

usage:
  next-version.py            現在値・次の値・タグ名を表示（何も書き換えない）
  next-version.py --apply    gradle.properties を書き換える

exit code:
  0  正常
  1  version が semver でない / -SNAPSHOT が付いている / タグが既に存在する
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip()
PROPS = os.path.join(ROOT, "gradle.properties")


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="gradle.properties を書き換える")
    args = ap.parse_args()

    if not ROOT:
        fail("git リポジトリの中で実行してください")

    text = open(PROPS, encoding="utf-8").read()
    m = re.search(r"^version=(.+)$", text, re.M)
    if not m:
        fail(f"{PROPS} に version= がありません")
    current = m.group(1).strip()

    if not re.fullmatch(r"\d+\.\d+\.\d+", current):
        fail(f"version={current} は X.Y.Z 形式ではありません。"
             " このリポジトリは -SNAPSHOT を使いません。勝手に直さず報告してください。")

    major, minor, patch = (int(p) for p in current.split("."))
    nxt = f"{major}.{minor}.{patch + 1}"
    tag = nxt  # タグ名は version と同一（v は付けない）

    local = subprocess.run(["git", "tag", "--list", tag],
                           capture_output=True, text=True, cwd=ROOT).stdout.strip()
    remote = subprocess.run(["git", "ls-remote", "--tags", "origin", tag],
                            capture_output=True, text=True, cwd=ROOT).stdout.strip()
    if local or remote:
        fail(f"タグ {tag} は既に存在します（local={bool(local)} remote={bool(remote)}）。"
             " 公開済みタグは動かさず、止めて報告してください。")

    if args.apply:
        open(PROPS, "w", encoding="utf-8").write(
            re.sub(r"^version=.+$", f"version={nxt}", text, count=1, flags=re.M))
        print(f"applied: {PROPS} version={nxt}")

    print(f"current={current}")
    print(f"next={nxt}")
    print(f"tag={tag}")


if __name__ == "__main__":
    main()
