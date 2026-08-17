#!/usr/bin/env python3
"""settle-prs.sh の結果からリリースコミットのメッセージを組み立てる。

このワークフローの成果物はコミットログである。BOM のバージョンだけを見ても、何が
どういう根拠で入ったのかは分からない。git log にレビュー内容が残っていれば、後から
「なぜこのバージョンなのか」を追える。Actions のログは 90 日で消える。

3 つの見出しは常に全部出す。該当が無ければ「なし」と書く。見出しごと省くと、後から
読んだ人には「該当が無かった」のか「調べていない」のか区別がつかない。

usage:
  build-release-notes.py --results results.jsonl --version 1.0.1 --out notes.txt
"""
import argparse
import json
import sys

MODEL_NOTE = "レビューは codex-fugu (fugu-cyber) が PR ごとに実行しました。"

HELD_OUTCOME_SUFFIX = {
    "closed": "（クローズ済み）",
    "left_open": "（PR は open のまま）",
    "dry-run": "（dry-run のため未処理）",
}


def cell(text):
    """Markdown の表の 1 セルに収める。改行と | が入ると表が壊れる。"""
    return " ".join(str(text).split()).replace("|", "\\|") or "-"


def table(header, rows):
    if not rows:
        return "なし"
    out = ["| " + " | ".join(header) + " |",
           "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.results, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    merged, held, unverified = [], [], []

    for r in sorted(records, key=lambda r: r["pr"]):
        pr = f"#{r['pr']}"
        updates = r.get("updates") or r.get("title") or ""

        if r.get("outcome") == "merged":
            merged.append([pr, updates, r.get("checked", "")])
        else:
            reason = r.get("reason", "")
            suffix = HELD_OUTCOME_SUFFIX.get(r.get("outcome"), "")
            held.append([pr, updates, f"{reason}{suffix}"])

        for item in r.get("unverified") or []:
            unverified.append(f"- {pr}: {' '.join(str(item).split())}")

    if not merged:
        print("ERROR: マージした PR が 1 件も無い。バージョンを上げる理由が無いので"
              " リリースコミットは作らない。", file=sys.stderr)
        return 1

    body = "\n".join([
        f"Bump version to {args.version}",
        "",
        "## マージした PR",
        "",
        table(["PR", "更新内容", "確認したこと"], merged),
        "",
        "## 保留した PR",
        "",
        table(["PR", "更新内容", "保留した理由"], held),
        "",
        "## 確認できなかったこと",
        "",
        "\n".join(unverified) if unverified else "なし",
        "",
        MODEL_NOTE,
        "",
    ])

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(body)
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
