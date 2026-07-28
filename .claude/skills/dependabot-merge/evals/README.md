# dependabot-merge の評価ハーネス

GitHub に触らずにスキルを検証するための一式です。`origin` をローカルの bare
リポジトリにし、`gh` を差し替えることで、マージ・タグ・push まで本物の git
操作として実行しつつ、外部には一切影響しません。

`gh api` と `gh release` は本物の gh に委譲するので、脆弱性照会と上流差分は
ライブのデータを見ます。ここを模擬すると検証の意味が無くなるためです。

## 使い方

```bash
# fixture を作る（scenario は clean / vulnerable / major_conflict）
python3 setup.py vulnerable /tmp/fx

# 差し替えた gh を使う
export FIXTURE_DIR=/tmp/fx
export PATH=$(pwd):$PATH      # この評価ディレクトリの gh を先に見せる

cd /tmp/fx/repo
# ここでスキルを実行させる

# 採点（レポートではなく git の実状態を見る）
python3 grade.py <config_dir>
```

## シナリオ

| scenario | 内容 | 期待 |
| --- | --- | --- |
| `clean` | ktor 3.5.0->3.5.1、ktlint 1.7.1->1.8.0 | 両方マージ、1.0.1 へ |
| `vulnerable` | snakeyaml 1.30->1.33（GHSA-mjmj-j48q-9wg2 の範囲内に留まる） | 保留。上流が GitHub に無いので「確認できなかったこと」も問う |
| `major_conflict` | kotlin-logging 7->8（メジャー）、kotest と ktor が隣接行で競合 | メジャーは保留、競合は @dependabot rebase で解消 |

バージョンはすべて実在するものを使っています。捏造したバージョンにすると
上流差分の確認が実行されず、スキルの中核が検証されないまま通ってしまいます。

## 注意

スキルはセッション単位で登録されるため、fixture から `.claude/skills/` を
消しても「スキルなし」の比較対象にはなりません。A/B を取るには、そのスキルが
登録されていないプロジェクトでセッションを開始してください。
