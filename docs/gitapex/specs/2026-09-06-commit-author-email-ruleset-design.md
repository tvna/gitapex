# commit_author_email_pattern/committer_email_patternルール導入の設計

## ステータス

Design-only。`.github/rulesets/main.json`は一切変更していない。issue未起票(設計段階)。

## 発端

`https://github.com/tvna/gitapex/commits?author=vsajan` の調査依頼から発覚: issue #1375を実装したPR #1380(tvna作成・マージ済み、mainに統合済み)の57コミット中44件が、GitHub上「vsajan」という無関係な第三者アカウントの成果として表示されていた。

## Facts(一次資料で確認済み)

1. **表示の原因はauthor情報、コード内容ではない**: 該当44コミットのgit commit author/committerは`t <t@t.com>`。GitHubは「コミットのメールアドレスとGitHubアカウント登録メールの一致」だけでアカウントを紐付ける仕組みを持つ(GitHub公式ドキュメント`why-are-my-commits-linked-to-the-wrong-user`で確認)。同ドキュメントは「誤った紐付けがあってもリポジトリへのアクセス権は付与されない」と明記しており、`list_repository_collaborators`でもvsajanはコラボレーターに含まれないことを確認した。
2. **PR #1380の作成者・マージ者は共にtvna本人**(`user.login: tvna`, `merged_by: tvna`)。通常のMerge commit戦略でmainに統合済み。diffの変更ファイルは5件(`hooks/gitapex_check_bash_safety.py`等)のみで、workflow編集・依存関係追加・governance file改変・typosquat・instruction-bearingコンテンツ等の兆候はなし。
3. **実際の署名状況を`git log --show-signature`/`git cat-file`で直接確認**: PR #1380の全コミット(Claude名義・`t@t.com`名義とも)は未署名。一方、tvna自身のGitHub Web UI経由マージコミットはGitHub自身のRSA鍵で署名済み。現在のクラウド作業環境(このセッション)は`/tmp/code-sign`(Anthropic側`environment-manager`)経由で実際にSSH署名データを生成することをテストコミットの`gpgsig`ヘッダーで確認したが、この鍵がGitHub側のどのアカウントに登録され「Verified」と認識されるかは本セッションの権限では確認不能(未確認)。
4. **GitHub Repository Rulesetsには、この種の誤帰属に直接効く2つのネイティブルールが存在する**(GitHub REST API `rules[].type`列一次資料で確認): `commit_author_email_pattern`/`committer_email_pattern`(`operator`+`pattern`+`negate`でauthor/committerメールを正規表現制限)と`required_signatures`(パラメータなし、未署名コミットを含むPRのマージ自体をブロックすると一次情報で確認)。
5. **このリポジトリは既にGitHub Repository Rulesetをgit管理のsource-of-truthとして運用している**(issue #439由来、`.github/rulesets/main.json` + `.github/scripts/_gitapex_rulesets.py` + `apply-rulesets.yml`/`ruleset-verify.yml`)。現状の`main.json`には`deletion`/`non_fast_forward`/`pull_request`/`required_status_checks`のみで、author/committerメールや署名に関するルールは無い。既存の`required_status_checks`はcontext一覧をこの1ファイルに直接列挙する流儀であり、専用の外部リストファイルの前例はない。
6. **オープン中の17件のPR(#1825, #1821, #1819, #1810, #1803, #1793, #1525, #1524, #1523, #1522, #1521, #1416, #1381, #1298, #1267, #775, #644)全体を`git log --pretty='%an <%ae> / %cn <%ce>' base..head`で突合済み**: author/committerは以下4パターンのみ、`t@t.com`は0件。
   - `Claude <noreply@anthropic.com>` / `Claude <noreply@anthropic.com>`
   - `Tsubasa Nagano <31282861+tvna@users.noreply.github.com>` / `GitHub <noreply@github.com>`
   - `Tsubasa Nagano <31282861+tvna@users.noreply.github.com>` / `Tsubasa Nagano <31282861+tvna@users.noreply.github.com>`
   - `dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>` / `GitHub <noreply@github.com>`

## 提案する設計

`.github/rulesets/main.json`の`rules`配列に、既存の4ルールと同じ並びで以下2ルールを追加する(パラメータの`pattern`はこの4パターンをORでカバーする正規表現、専用の外部リストファイルは新設しない):

```json
{
  "type": "commit_author_email_pattern",
  "parameters": {
    "operator": "regex",
    "pattern": "^(noreply@anthropic\\.com|31282861\\+tvna@users\\.noreply\\.github\\.com|49699333\\+dependabot\\[bot\\]@users\\.noreply\\.github\\.com)$"
  }
},
{
  "type": "committer_email_pattern",
  "parameters": {
    "operator": "regex",
    "pattern": "^(noreply@anthropic\\.com|31282861\\+tvna@users\\.noreply\\.github\\.com|noreply@github\\.com|49699333\\+dependabot\\[bot\\]@users\\.noreply\\.github\\.com)$"
  }
}
```

(`negate`は許可リストとして機能する向き、実装前にOpenAPI仕様で最終確認 -- Open Questions参照。上記2つの`pattern`が非対称なのは、Fact 6のとおりauthor側に`noreply@github.com`が出現しないため。)

## Non-goals(この設計では扱わない、意図的)

- **`required_signatures`**: 署名鍵がGitHub側のどのアカウントに登録され「Verified」と認識されるかが未確認(Fact 3)なため、今回は見送る。鍵登録状況を確認したうえで別issueで扱う。パターンチェックだけではメールアドレス文字列のなりすまし自体は防げない(暗号的な身元証明ではない)ため、根絶にはならない残存リスクとして別途扱う。
- 専用の許可リストファイルの新設(Fact 5のとおり既存流儀に合わせ`main.json`直書きとする)。

## Open Questions

- `commit_author_email_pattern`/`committer_email_pattern`の`negate`パラメータの正確な挙動(「マッチで失敗」か「非マッチで失敗」か)が、生成AI要約経由の情報にとどまっている。実装時にGitHub REST APIのOpenAPI定義(一次情報)で確定させる。
- vsajanアカウントが`t@t.com`を登録メールに持っているという推測自体は、GitHubがメールを非公開にするため今後も直接確認できない。
