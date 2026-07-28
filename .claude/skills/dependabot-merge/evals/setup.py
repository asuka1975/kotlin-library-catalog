#!/usr/bin/env python3
"""Build an isolated fixture (bare origin + clone + PR branches) for one eval run.

All version pairs are real and published, and every upstream repo except
snakeyaml (bitbucket) supports the GitHub compare API — so the "read the
upstream diff" step is actually exercisable.

usage: setup.py <scenario> <dest_dir>
"""
import json
import os
import shutil
import subprocess
import sys

REPO = "/home/asuka1975/work/kotlin/kotlin-library-catalog"

SCENARIOS = {
    # 健全な更新のみ。ktor と ktlint は 3 行離れているので競合しない（実測済み）。
    "clean": {
        "seed": [('val ktor = "3.5.1"', 'val ktor = "3.5.0"'),
                 ('val ktlint = "1.8.0"', 'val ktlint = "1.7.1"')],
        "prs": [
            {"number": 11,
             "title": "Bump the ktor group with 4 updates",
             "headRefName": "dependabot/gradle/ktor-06f4d8a3ee",
             "old_line": 'val ktor = "3.5.0"',
             "new_line": 'val ktor = "3.5.1"',
             "body": "Bumps the ktor group with 4 updates: "
                     "[io.ktor:ktor-client-core](https://github.com/ktorio/ktor), "
                     "io.ktor:ktor-client-cio, io.ktor:ktor-client-content-negotiation "
                     "and io.ktor:ktor-serialization-kotlinx-json.\n"
                     "Updates `io.ktor:ktor-client-core` from 3.5.0 to 3.5.1\n"},
            {"number": 12,
             "title": "Bump the ktlint group with 3 updates",
             "headRefName": "dependabot/gradle/ktlint-3a91cc",
             "old_line": 'val ktlint = "1.7.1"',
             "new_line": 'val ktlint = "1.8.0"',
             "body": "Bumps the ktlint group with 3 updates: "
                     "[com.pinterest.ktlint:ktlint-cli](https://github.com/pinterest/ktlint), "
                     "com.pinterest.ktlint:ktlint-rule-engine and "
                     "com.pinterest.ktlint:ktlint-ruleset-standard.\n"
                     "Updates `com.pinterest.ktlint:ktlint-cli` from 1.7.1 to 1.8.0\n"},
        ],
    },
    # snakeyaml 1.30 -> 1.33 は GHSA-mjmj-j48q-9wg2 (patched 2.0) の範囲内に留まる。
    # 上流が bitbucket なので GitHub の compare は取れず、その事実を報告できるかも問う。
    "vulnerable": {
        "seed": [('val kotest = "6.2.3"', 'val kotest = "6.2.2"'),
                 ('        api("io.mockk:mockk:1.14.11")',
                  '        api("io.mockk:mockk:1.14.11")\n'
                  '        api("org.yaml:snakeyaml:1.30")')],
        "prs": [
            {"number": 21,
             "title": "Bump the kotest group with 3 updates",
             "headRefName": "dependabot/gradle/kotest-4ab8d1",
             "old_line": 'val kotest = "6.2.2"',
             "new_line": 'val kotest = "6.2.3"',
             "body": "Bumps the kotest group with 3 updates: "
                     "[io.kotest:kotest-runner-junit5](https://github.com/kotest/kotest), "
                     "io.kotest:kotest-assertions-core and io.kotest:kotest-property.\n"
                     "Updates `io.kotest:kotest-runner-junit5` from 6.2.2 to 6.2.3\n"},
            {"number": 22,
             "title": "Bump org.yaml:snakeyaml from 1.30 to 1.33",
             "headRefName": "dependabot/gradle/org.yaml-snakeyaml-1.33",
             "old_line": 'api("org.yaml:snakeyaml:1.30")',
             "new_line": 'api("org.yaml:snakeyaml:1.33")',
             "body": "Bumps [snakeyaml](https://bitbucket.org/snakeyaml/snakeyaml) "
                     "from 1.30 to 1.33.\n"
                     "<details><summary>Commits</summary>\n"
                     "See full diff in compare view\n</details>\n"},
        ],
    },
    # kotlin-logging 7 -> 8 はメジャーアップなので保留。kotest と ktor は隣接行なので
    # 片方をマージすると他方が競合し、@dependabot rebase が要る。
    "major_conflict": {
        "seed": [('val ktor = "3.5.1"', 'val ktor = "3.5.0"'),
                 ('val kotest = "6.2.3"', 'val kotest = "6.2.2"'),
                 ('api("io.github.oshai:kotlin-logging:8.0.4")',
                  'api("io.github.oshai:kotlin-logging:7.0.7")')],
        "prs": [
            {"number": 31,
             "title": "Bump io.github.oshai:kotlin-logging from 7.0.7 to 8.0.4",
             "headRefName": "dependabot/gradle/io.github.oshai-kotlin-logging-8.0.4",
             "old_line": 'api("io.github.oshai:kotlin-logging:7.0.7")',
             "new_line": 'api("io.github.oshai:kotlin-logging:8.0.4")',
             "body": "Bumps [kotlin-logging](https://github.com/oshai/kotlin-logging) "
                     "from 7.0.7 to 8.0.4.\n"},
            {"number": 32,
             "title": "Bump the kotest group with 3 updates",
             "headRefName": "dependabot/gradle/kotest-4ab8d1",
             "old_line": 'val kotest = "6.2.2"',
             "new_line": 'val kotest = "6.2.3"',
             "body": "Bumps the kotest group with 3 updates: "
                     "[io.kotest:kotest-runner-junit5](https://github.com/kotest/kotest), "
                     "io.kotest:kotest-assertions-core and io.kotest:kotest-property.\n"
                     "Updates `io.kotest:kotest-runner-junit5` from 6.2.2 to 6.2.3\n"},
            {"number": 33,
             "title": "Bump the ktor group with 4 updates",
             "headRefName": "dependabot/gradle/ktor-06f4d8a3ee",
             "old_line": 'val ktor = "3.5.0"',
             "new_line": 'val ktor = "3.5.1"',
             "body": "Bumps the ktor group with 4 updates: "
                     "[io.ktor:ktor-client-core](https://github.com/ktorio/ktor), "
                     "io.ktor:ktor-client-cio, io.ktor:ktor-client-content-negotiation "
                     "and io.ktor:ktor-serialization-kotlinx-json.\n"
                     "Updates `io.ktor:ktor-client-core` from 3.5.0 to 3.5.1\n"},
        ],
    },
}


def git(*args, cwd, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check,
                          capture_output=True, text=True)


def main():
    scenario, dest = sys.argv[1], sys.argv[2]
    spec = SCENARIOS[scenario]
    prs = spec["prs"]

    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    origin = os.path.join(dest, "origin.git")
    build = "build.gradle.kts"

    # 現在のリポジトリを種にして、送り先がローカルだけの origin を作る
    seed = os.path.join(dest, "_seed")
    git("clone", "-q", REPO, seed, cwd=dest)
    git("config", "user.email", "dependabot[bot]@users.noreply.github.com", cwd=seed)
    git("config", "user.name", "dependabot[bot]", cwd=seed)

    # main を「更新前」の状態に戻す
    path = os.path.join(seed, build)
    text = open(path).read()
    for old, new in spec["seed"]:
        assert old in text, f"seed target not found: {old!r}"
        text = text.replace(old, new)
    open(path, "w").write(text)
    git("commit", "-qam", "Set fixture baseline", cwd=seed)

    git("init", "-q", "--bare", "-b", "main", origin, cwd=dest)
    git("remote", "remove", "origin", cwd=seed, check=False)
    git("remote", "add", "origin", origin, cwd=seed)
    git("push", "-q", "origin", "main", cwd=seed)

    for pr in prs:
        git("checkout", "-q", "-B", pr["headRefName"], "main", cwd=seed)
        text = open(path).read()
        assert pr["old_line"] in text, f"{pr['old_line']!r} not found"
        open(path, "w").write(text.replace(pr["old_line"], pr["new_line"]))
        git("commit", "-qam", pr["title"], cwd=seed)
        git("push", "-q", "origin", pr["headRefName"], cwd=seed)
    git("checkout", "-q", "main", cwd=seed)
    shutil.rmtree(seed)

    work = os.path.join(dest, "work")
    git("clone", "-q", origin, work, cwd=dest)
    git("config", "user.email", "bot@example.com", cwd=work)
    git("config", "user.name", "gh-mock", cwd=work)

    # エージェントが作業するチェックアウト
    repo = os.path.join(dest, "repo")
    git("clone", "-q", origin, repo, cwd=dest)
    git("config", "user.email", "asuka1975@example.com", cwd=repo)
    git("config", "user.name", "asuka1975", cwd=repo)

    base = git("rev-parse", "main", cwd=origin).stdout.strip()
    state = {
        "base_sha": base,
        "prs": [dict(p, file=build, state="OPEN",
                     url=f"https://github.com/asuka1975/kotlin-library-catalog/pull/{p['number']}")
                for p in prs],
    }
    with open(os.path.join(dest, "state.json"), "w") as f:
        json.dump(state, f, indent=2)

    print(f"fixture ready: {dest}  base={base[:8]}  PRs={[p['number'] for p in prs]}")


if __name__ == "__main__":
    main()
