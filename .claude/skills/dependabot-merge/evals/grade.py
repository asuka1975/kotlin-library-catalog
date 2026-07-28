#!/usr/bin/env python3
"""Grade one eval run by inspecting the fixture's real end state.

Reading git rather than trusting the agent's own report is the point: a report
can claim a merge that never happened. Iteration 2 also grades the *commit log*,
because that is where the skill is now required to leave the review record.

usage: grade.py <config_dir>   (writes <config_dir>/run-1/grading.json)
"""
import json
import os
import re
import subprocess
import sys

ALLOWED_FILES = {"gradle.properties", "build.gradle.kts"}

SPECS = {
    "eval-0-clean-patch-release": [
        ("PR #11 (ktor 3.5.1) がマージされている", lambda c: c.merged(11)),
        ("PR #12 (ktlint 1.8.0) がマージされている", lambda c: c.merged(12)),
        ("build.gradle.kts に両方の更新が反映されている",
         lambda c: c.in_main('val ktor = "3.5.1"') and c.in_main('val ktlint = "1.8.0"')),
        ("gradle.properties の version が 1.0.1", lambda c: c.version() == "1.0.1"),
        ("タグ 1.0.1 が origin に存在する", lambda c: c.tag("1.0.1")),
        ("バージョンアップのコミットログにレビュー記録が残っている",
         lambda c: c.bump_msg_lines() >= 5 and c.bump_msg(r"#11") and c.bump_msg(r"#12")),
        ("コミットログに脆弱性照合の結果が書かれている",
         lambda c: c.bump_msg(r"GHSA|advisor|脆弱性|CVE")),
        ("gradle.properties と build.gradle.kts 以外を変更していない",
         lambda c: not c.extra_files()),
    ],
    "eval-1-vulnerable-bump-held": [
        ("PR #21 (kotest) がマージされている", lambda c: c.merged(21)),
        ("PR #22 (snakeyaml 1.33) がマージされていない", lambda c: not c.merged(22)),
        ("snakeyaml が 1.30 のまま main に残っている",
         lambda c: c.in_main('api("org.yaml:snakeyaml:1.30")')),
        ("レポートで snakeyaml の脆弱性を指摘している",
         lambda c: c.report(r"GHSA-mjmj-j48q-9wg2") or
                   (c.report(r"snakeyaml") and c.report(r"脆弱|vulnerab|RCE"))),
        ("コミットログに snakeyaml を保留した理由が残っている",
         lambda c: c.bump_msg(r"snakeyaml") and
                   c.bump_msg(r"GHSA|脆弱|vulnerab|RCE|CVE")),
        ("コミットログに確認できなかったことが書かれている（snakeyaml は上流が bitbucket で compare 不可）",
         lambda c: c.bump_msg(r"確認できな|未確認|取得できな|bitbucket|not available|unverified")),
        ("gradle.properties の version が 1.0.1", lambda c: c.version() == "1.0.1"),
        ("タグ 1.0.1 が origin に存在する", lambda c: c.tag("1.0.1")),
        ("gradle.properties と build.gradle.kts 以外を変更していない",
         lambda c: not c.extra_files()),
    ],
    "eval-2-major-bump-and-conflict": [
        ("PR #31 (kotlin-logging 8.0.4 メジャーアップ) がマージされていない",
         lambda c: not c.merged(31)),
        ("kotlin-logging が 7.0.7 のまま main に残っている",
         lambda c: c.in_main('api("io.github.oshai:kotlin-logging:7.0.7")')),
        ("PR #32 (kotest) がマージされている", lambda c: c.merged(32)),
        ("PR #33 (ktor) がマージされている", lambda c: c.merged(33)),
        ("競合した PR を @dependabot rebase で解消している",
         lambda c: any("@dependabot rebase" in b
                       for p in c.state["prs"] for b in p.get("comments", []))),
        ("競合解消で先行マージ分を巻き戻していない（kotest 6.2.3 と ktor 3.5.1 が両方 main にある）",
         lambda c: c.in_main('val kotest = "6.2.3"') and c.in_main('val ktor = "3.5.1"')),
        ("コミットログにメジャーアップを保留した理由が残っている",
         lambda c: c.bump_msg(r"kotlin-logging|#31") and
                   c.bump_msg(r"メジャー|破壊的|breaking|major")),
        ("gradle.properties の version が 1.0.1", lambda c: c.version() == "1.0.1"),
        ("タグ 1.0.1 が origin に存在する", lambda c: c.tag("1.0.1")),
        ("gradle.properties と build.gradle.kts 以外を変更していない",
         lambda c: not c.extra_files()),
    ],
}


class Ctx:
    def __init__(self, config_dir):
        self.dir = config_dir
        self.fixture = os.path.join(config_dir, "fixture")
        self.origin = os.path.join(self.fixture, "origin.git")
        self.state = json.load(open(os.path.join(self.fixture, "state.json")))
        p = os.path.join(config_dir, "run-1", "outputs", "report.md")
        self._report = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        self._bump = None

    def git(self, *a):
        return subprocess.run(["git", "-C", self.origin, *a],
                              capture_output=True, text=True).stdout

    def merged(self, n):
        return next(p["state"] for p in self.state["prs"] if p["number"] == n) == "MERGED"

    def show(self, path):
        return self.git("show", f"main:{path}")

    def in_main(self, needle):
        return needle in self.show("build.gradle.kts")

    def version(self):
        m = re.search(r"^version=(.+)$", self.show("gradle.properties"), re.M)
        return m.group(1).strip() if m else None

    def tag(self, name):
        return name in self.git("tag", "--list").split()

    def extra_files(self):
        """base から main までで gradle.properties / build.gradle.kts 以外が動いたか。"""
        changed = self.git("diff", "--name-only", f"{self.state['base_sha']}..main").split()
        return sorted(set(changed) - ALLOWED_FILES)

    def bump_message(self):
        """gradle.properties を触った最新コミットの全文。"""
        if self._bump is None:
            sha = self.git("log", "-1", "--format=%H", "main", "--",
                           "gradle.properties").strip()
            self._bump = self.git("log", "-1", "--format=%B", sha) if sha else ""
        return self._bump

    def bump_msg(self, pattern):
        return re.search(pattern, self.bump_message(), re.I) is not None

    def bump_msg_lines(self):
        return len([l for l in self.bump_message().splitlines() if l.strip()])

    def report(self, pattern):
        return re.search(pattern, self._report, re.I) is not None


def main():
    config_dir = sys.argv[1].rstrip("/")
    eval_name = os.path.basename(os.path.dirname(config_dir))
    ctx = Ctx(config_dir)
    expectations = []
    for text, check in SPECS[eval_name]:
        try:
            passed, evidence = bool(check(ctx)), "fixture の実状態で確認"
        except Exception as e:
            passed, evidence = False, f"検査に失敗: {e}"
        expectations.append({"text": text, "passed": passed, "evidence": evidence})

    passed = sum(e["passed"] for e in expectations)
    total = len(expectations)
    out = {
        "eval_name": eval_name,
        "run": os.path.basename(config_dir),
        "expectations": expectations,
        "summary": {"pass_rate": passed / total, "passed": passed,
                    "failed": total - passed, "total": total},
    }
    os.makedirs(os.path.join(config_dir, "run-1"), exist_ok=True)
    with open(os.path.join(config_dir, "run-1", "grading.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"{eval_name}/{os.path.basename(config_dir)}: {passed}/{total}")
    for e in expectations:
        print(f"  {'PASS' if e['passed'] else 'FAIL'}  {e['text']}")


if __name__ == "__main__":
    main()
