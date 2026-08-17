#!/usr/bin/env bash
#
# レビュージョブが出した評決に従って Dependabot PR を片付ける。
#
# 判断はしない。ここは評決を実行するだけの場所で、MERGE なら（ビルドが通れば）
# マージ、HOLD ならクローズ、評決が無ければ何もせず open のまま残す。
# 結果は 1 PR 1 行の JSON Lines として $RESULTS に書き出し、リリースコミットの
# メッセージ生成に渡す。
#
# 環境変数:
#   VERDICT_DIR  評決 JSON (<PR番号>.json) が置かれたディレクトリ   既定: artifacts
#   PRS_JSON     gh pr list の出力                                  既定: prs.json
#   RESULTS      結果の書き出し先 (JSON Lines)                      既定: results.jsonl
#   DRY_RUN      true ならマージもクローズもせず記録だけ            既定: false
#   FUGU_MODEL   クローズ理由のコメントに書くモデル名               既定: Fugu
#   GH_TOKEN     pull-requests:write / contents:write のトークン

set -euo pipefail

VERDICT_DIR=${VERDICT_DIR:-artifacts}
PRS_JSON=${PRS_JSON:-prs.json}
RESULTS=${RESULTS:-results.jsonl}
DRY_RUN=${DRY_RUN:-false}
MODEL=${FUGU_MODEL:-Fugu}

# Dependabot の rebase 待ち。SKILL.md と同じく 10 分で諦める。
POLL_INTERVAL=${POLL_INTERVAL:-30}
POLL_ATTEMPTS=${POLL_ATTEMPTS:-20}

: > "$RESULTS"

log() { printf '%s\n' "$*"; }

# 評決を読む。ファイルが無い / 壊れている / verdict が MERGE|HOLD でない場合は
# ERROR を返す。ERROR は「調べていない」であって「問題なし」ではないので、
# その PR には一切手を触れない。
read_verdict() {
  local pr=$1 file="$VERDICT_DIR/$1.json"
  if [ ! -f "$file" ] || ! jq -e . "$file" >/dev/null 2>&1; then
    jq -n --argjson pr "$pr" '{
      pr: $pr, verdict: "ERROR",
      reason: "レビュー結果を取得できなかった",
      updates: "", checked: "",
      unverified: ["レビュー自体が完了していないため、脆弱性・上流差分ともに未確認"]
    }'
    return
  fi
  jq --argjson pr "$pr" '{
    pr: $pr,
    verdict: (if (.verdict == "MERGE" or .verdict == "HOLD") then .verdict else "ERROR" end),
    reason: (.reason // ""), updates: (.updates // ""), checked: (.checked // ""),
    unverified: (.unverified // [])
  }' "$file"
}

record() { # $1: 評決 JSON, $2: outcome
  local title
  title=$(jq -r --argjson pr "$(jq -r .pr <<<"$1")" \
    '.[] | select(.number == $pr) | .title' "$PRS_JSON")
  jq -c --arg outcome "$2" --arg title "$title" \
    '. + {outcome: $outcome, title: $title}' <<<"$1" >> "$RESULTS"
}

# マージ可能になるまで待つ。競合していたら Dependabot に作り直させる。
# 自分で競合を解決して force push しないこと。Dependabot の PR を書き換えると
# Dependabot 側の追跡が壊れ、次回以降おかしな PR が出る。
wait_mergeable() {
  local pr=$1 rebased=0 state i
  for ((i = 1; i <= POLL_ATTEMPTS; i++)); do
    state=$(gh pr view "$pr" --json mergeable --jq .mergeable)
    case "$state" in
      MERGEABLE)
        return 0
        ;;
      CONFLICTING)
        if [ "$rebased" -eq 0 ]; then
          log "  #$pr は競合している。@dependabot rebase を依頼する"
          gh pr comment "$pr" --body "@dependabot rebase"
          rebased=1
        fi
        ;;
      *)
        # UNKNOWN。直前のマージを受けて GitHub が再計算している最中。
        ;;
    esac
    sleep "$POLL_INTERVAL"
  done
  log "  #$pr は ${POLL_ATTEMPTS}x${POLL_INTERVAL}s 待っても MERGEABLE にならなかった"
  return 1
}

# PR のブランチをビルドする。CI が無いリポジトリなので、ここが唯一の検証。
# 途中で失敗しても main に戻って ci-verify を消す。&& で繋いでいるのは、
# fetch や checkout が失敗したまま ./gradlew まで進むと、別のブランチを
# ビルドして「通った」と誤認するため。
build_branch() {
  local branch=$1 rc=0
  git fetch --force origin "$branch:refs/heads/ci-verify" \
    && git checkout ci-verify \
    && ./gradlew --no-daemon build publishToMavenLocal \
    || rc=$?
  git checkout main || true
  git branch -D ci-verify >/dev/null 2>&1 || true
  return "$rc"
}

# ---- 1. 評決を集める --------------------------------------------------------

mapfile -t numbers < <(jq -r '.[].number' "$PRS_JSON")
declare -a to_merge=()

for pr in "${numbers[@]}"; do
  verdict_json=$(read_verdict "$pr")
  verdict=$(jq -r .verdict <<<"$verdict_json")
  reason=$(jq -r .reason <<<"$verdict_json")
  log "#$pr: $verdict — $reason"

  case "$verdict" in
    MERGE)
      to_merge+=("$pr")
      ;;
    HOLD)
      if [ "$DRY_RUN" = "true" ]; then
        log "  [dry-run] クローズしない"
        record "$verdict_json" "dry-run"
      else
        gh pr comment "$pr" --body "$(printf '%s によるレビューの結果、この更新は取り込まずクローズします。\n\n**理由**: %s\n\n判断が誤っている場合は PR を reopen してください。' "$MODEL" "$reason")"
        gh pr close "$pr"
        record "$verdict_json" "closed"
      fi
      ;;
    *)
      log "  評決が無いので触らない（open のまま残す）"
      record "$verdict_json" "left_open"
      ;;
  esac
done

# ---- 2. マージする ----------------------------------------------------------
#
# 1 件ずつ処理する。共有バージョンの val がファイル冒頭に固まって並んでいるため、
# squash マージの後、隣接する行を触る PR は 3-way マージが解決できず競合する。

for pr in "${to_merge[@]}"; do
  verdict_json=$(read_verdict "$pr")
  branch=$(jq -r --argjson pr "$pr" '.[] | select(.number == $pr) | .headRefName' "$PRS_JSON")

  if [ "$DRY_RUN" = "true" ]; then
    log "#$pr: [dry-run] $branch をビルドするだけでマージしない"
    if build_branch "$branch"; then
      record "$verdict_json" "dry-run"
    else
      record "$(jq '.verdict = "HOLD" | .reason = "ビルドが通らなかった" |
                    .unverified += ["ビルド失敗のため上流の妥当性以前に取り込めない"]' \
                 <<<"$verdict_json")" "dry-run"
    fi
    continue
  fi

  log "#$pr: マージ可能になるのを待つ"
  if ! wait_mergeable "$pr"; then
    record "$(jq '.verdict = "HOLD" |
                  .reason = "競合が解消されずマージできなかった（PR は open のまま）"' \
               <<<"$verdict_json")" "left_open"
    continue
  fi

  log "#$pr: $branch をビルドして確認する"
  if ! build_branch "$branch"; then
    log "  ビルドが通らないので HOLD 扱いにする"
    record "$(jq '.verdict = "HOLD" | .reason = "ビルドが通らなかった（PR は open のまま）" |
                  .unverified += ["ビルド失敗のため取り込み後の挙動は未確認"]' \
               <<<"$verdict_json")" "left_open"
    continue
  fi

  log "#$pr: マージする"
  gh pr merge "$pr" --squash --delete-branch
  git checkout main
  git pull --ff-only origin main
  record "$verdict_json" "merged"
done

log ""
log "結果:"
jq -r '"  #\(.pr) \(.outcome) (\(.verdict))"' "$RESULTS"
