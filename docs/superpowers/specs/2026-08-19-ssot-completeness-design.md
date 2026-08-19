# SSoT(ssot.json)の完全性: shadow gate問題と構造化の設計

> **本ファイルの由来(issue #1232でリポジトリに追加)**: この設計記録は、issue #1231/#1232双方が名前で参照している一次資料でありながら、これまでリポジトリにコミットされたことがなく、Claude Artifactとしてのみ存在していた。issue #1232の計画段階で「`ssot-completeness-design.md`がリポジトリに存在しない」という事実を発見し、依頼者から当該Artifact URLを提示されたことで解決した。原文のHTML本文をこのMarkdownへ機械変換した上で、この由来ノートのみを追記している(内容そのものへの加筆・要約・取捨選択は行っていない)。作成元セッションの正確な日時は本文中に記録されておらず不明(issue #1232時点で「数週間前」とだけ開示されている)。ファイル名の日付はこのコミットが行われた日を表し、分析が実施された日ではない。
>
> **重要な注意**: 本文中の「実データによるtargetバックフィル検証」節が示す57件中49件・kind別の項目数(107/56/21/14/10/9)は、あくまで**集計結果**であり、49件それぞれの個別`target`配列の値を列挙した表ではない(明示的に列挙されているのは、medium/ambiguousと判定された8件のidと理由のみ)。したがって、この文書を49件分の`target`値のコピー元として扱うことはできない -- issue #1232自身が要求する「ライブスクリプトに対する再検証」は、このファイルとの照合ではなく、各gateの実際のスクリプト/トリガーからの独立した再導出を意味する。

## ステータス

Design-only。`.gitapex/`配下のファイルは一切作成・変更していない。issue未起票(設計段階のため、これまでの記録群と同じ扱い)。

**追記(ultracodeワークフローによる実データ検証、2件の依頼を統合)**: 11エージェント構成のワークフロー(一次資料調査4件 + 57ゲート全件のバックフィル監査6バッチ + 統合1件)を実行し、次の2点を追加した。(A) 下記「提案する設計」の`target`スキーマ案を、実際の57ゲート全件に対して機械的にではなく人手相当の監査で後付けし、実行可能性を実データで検証(##実データによるtargetバックフィル検証)。(B) ご指摘の「多層防御として有効でなく、エージェントを非合理化させるブロッカーとして介在する実装をすべきでないゲート」という観点(non-gate)を、`evaluating-deterministic-gate-quality`スキルの既存フレームワーク(mechanism-fit test、dimension 21)と突き合わせ、そこに実在するギャップを4件の一次資料(全て直接fetch確認済み)で裏付けた上で新ディメンション案を提示(##non-gateの観点)。

## 発端

「ssot.jsonのidは自然言語によって確定しており、これが原因で書き漏らしをコードベースからしか探索できない」というご指摘。Windowsレジストリのようなネスト構造を前提に、SSoTの書き漏れをなくす方法を検討する。

## Facts(一次資料で確認済み)

1. **`id`は確かに構造を持たない**: `ssot.schema.json`で`id`のパターンは`^[a-z0-9]+(-[a-z0-9]+)*$`(kebab-caseの平坦な文字列、階層区切り文字は許可されない)。実際の57件のgate id(直接`jq`で確認済み)は`bash-cli-write-and-install-guard`・`skill-audit-disclosure`・`pr-title-convention`等、目的を説明する自然言語のスラッグで、共通の座標系を持たない。
2. **しかし、実際に「何を対象にしているか」を保持しているのは`id`ではなく`trigger`フィールド**: `trigger`は`{"type": "string", "minLength": 1}`、「a hook matcher, a workflow event, or a pytest collection path」を記述する自由記述の一文。例: `"trigger": "PreToolUse matcher mcp__github__merge_pull_request (hooks/hooks.json)"`。この「どのツール/ファイル/イベントを対象にするか」という、完全性チェックに使える唯一の情報が、機械比較できない散文に閉じ込められている。`id`が自然言語であること自体は症状であり、根本原因は`trigger`が構造化されていないことにある。
3. **gitapex自身が、この欠落を既に名指しで認識している(直接grepで発見)**: `.github/scripts/gitapex_scan_ssot_schema.py`のdocstringに次の記述がある(原文): *"It does not check the converse -- a real gate script with no registry entry at all (under-registration, a "shadow gate") is a known, accepted gap; see the PR that introduced this scanner for why that was left as a follow-up rather than folded in here."* -- 「shadow gate」という名前まで既についている、既知の未解決課題。
4. **`ssot-schema-drift`ゲート(`gitapex_scan_ssot_schema.py`)がチェックしているのは参照整合性のみ**: 「`gates[].script`の指す先が実在するファイルか」「`policy_refs[]`の指す先が実在する`policy_sources[].id`か」を検証する -- レジストリの**中の**ポインタが正しいかのチェックであり、レジストリの**外**(コードベース全体)に存在するのにレジストリに載っていないものを見つける仕組みではない。
5. **具体的な実例(このセッション内で既に発見済み)**: `hooks/hooks.json`のPreToolUseマッチャーには`mcp__github__merge_pull_request`が実在するが、`ssot.json`の57件のgateにこれを対象とするエントリは0件(前回セッションでgrepにより発見、今回`jq`で再確認)。
6. **同種のツール面全体を数え上げると、さらに範囲が広い(今回新たに確認)**: `hooks/hooks.json`が実際にPreToolUseで保護しているのは`mcp__github__`ツールのうち`create_pull_request`・`update_pull_request`・`issue_write`・`merge_pull_request`の4種のみ。この環境で呼び出し可能な他の書き込み系`mcp__github__*`ツール(`enable_pr_auto_merge`・`disable_pr_auto_merge`・`create_or_update_file`・`delete_file`・`push_files`・`pull_request_review_write`等)には、フックすら存在せず、当然`ssot.json`への登録もない。これらが「安全上問題ない」のか「単に誰も監査していない」のかは、現状のレジストリを読むだけでは区別できない。
7. **完全性チェックの前例は既に部分的に存在する(転用できる)**: `.github/scripts/gitapex_detect_changed_gate_scripts.py`は、「あるパスがgateかどうか」を4つの独立した規則の和集合(命名規則 ∪ レジストリ内の`script`参照 ∪ レジストリファイル自身 ∪ `hooks.json`の配線)で判定している。これは実質的に「レジストリに書かれているかどうかに依存しない、独立した"gateらしさ"の検出」であり、まさに書き漏れ検出に使える設計だが、現状は`skill-audit-disclosure`ゲート用に「diffで変更されたファイルがgateか」というスコープに限定されている。全リポジトリを対象にした常設のレジストリ完全性スキャンには一般化されていない。
8. **`registry-wiring-scan`ゲート**も同系統の前例: `.github/scripts/*.py`の登録済みCLIフラグがworkflowファイル側でも一致しているかを「単一の手書きテストを自己発見的スキャンへ一般化した」(issue #673/#674からissue #682への発展)もので、「1つの個別チェックを、リポジトリ全体を横断する自己発見的スキャンへ一般化する」という設計パターン自体はgitapex内に確立している。

## 診断の精緻化: 真因は`id`ではなく`trigger`の構造化欠如

ご指摘の通り「自然言語のidが原因で書き漏らしをコードベースからしか探索できない」という現象は正しい。ただし一次資料を踏まえると、`id`を階層化するだけでは効果が薄い。`id`は人間が読むための識別子であり、階層化しても「この階層のこのノードに何かが登録されている」ことは分かっても、「登録されているべきなのに登録されていないノード」を機械的に検出することはできない -- Windowsレジストリ自身がまさにこの限界を持つ(後述)。実際に書き漏れ検出へ効くのは、**「何を対象にしているか」を`trigger`の散文から取り出し、機械比較できる構造化フィールドにすること**である。

## Windowsレジストリとの類似性: 有効な点と、そのまま持ち込むと悪化する点

**有効な点**: レジストリのキー階層は、正確な葉のパスを知らなくても「このキー配下に何があるか」を列挙できる(`HKLM\SOFTWARE\Vendor\`配下を丸ごと見る、等)。現状の`ssot.json`は57件のidをアルファベット順に並べただけの平坦なリストで、この種のブラウズ可能性を一切持たない。

**そのまま持ち込むと悪化する点(2つ)**:

1. **レジストリ自体は完全性を保証しない**: Windowsのレジストリは「あるキーが存在すべきなのに存在しない」ことを自己検出する仕組みを持たない -- それを判定するのは、レジストリの外側にある独立した基準(インストーラのマニフェスト、ポリシーテンプレート等)である。階層化そのものが書き漏れを無くすのではなく、**独立に計算した「あるべき座標の集合」と実際の登録を突き合わせる仕組み**があって初めて書き漏れが可視化される。幸い、Facts 7の`gitapex_detect_changed_gate_scripts.py`がこの「独立に計算する」部分の実例を既に持っている。
2. **レジストリは厳密な単一親ツリーだが、gitapexの実データは元々多次元**: `cluster`は既に文字列または配列(複数クラスタに同時所属するgateが実在する、例: `bash-cli-write-and-install-guard`は`["outward-hygiene", "github-operations"]`)、`planes`も配列(pretooluse+ciの両方で稼働するgateが多数)。Windowsレジストリ流の「1つの親の下にぶら下がる」という厳密な木構造をそのまま持ち込むと、複数の対象・複数の観点を持つgateに無理な単一の親を選ばせることになり、既に上手く機能している多重所属の表現力を後退させる。木構造ではなく、ファセット(多次元タグ)構造を推奨する。

## 提案する設計

```
"target": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["kind", "ref"],
    "properties": {
      "kind": {"enum": [
        "mcp-tool", "bash-pattern", "file-glob", "workflow-event",
        "github-native", "cross-registry-consistency"
      ]},
      "ref": {"type": "string"}
    }
  }
}
```

1. 例: `merge-pull-request-block`(未登録、提案中のid)なら`target: [{"kind": "mcp-tool", "ref": "mcp__github__merge_pull_request"}]`。`trigger`は引き続き人間向けの散文として残す(役割を分離するだけで、既存フィールドは壊さない)。`cross-registry-consistency`は初期提案には無かったが、実データのバックフィル(次節)で57件中21件のtarget項目がこの種類を必要とすると判明したため追加した -- 詳細は次節。
2. **`gitapex_detect_changed_gate_scripts.py`の4規則和集合パターンを一般化し、常設の完全性スキャンを新設する**: 「diffで変更されたファイル」ではなく「独立に列挙可能な対象領域全体」を走査する。最初の対象領域として**MCPツール面**を選ぶ(この環境が呼び出し可能な`mcp__github__*`等のツール一覧は、最も機械的に列挙しやすい)。各ツールについて、`gates[].target[]`に`{"kind": "mcp-tool", "ref": "<そのツール名>"}`が1件でもあるかを確認し、無ければ`shadow gate候補`としてレポートする(gitapex自身が既に使っている名前をそのまま採用)。書き込み系ツールに対象が1件も無ければ警告、`kind: "mcp-tool"`だが読み取り専用ツールは対象外、といった判定ルールは新設スキャン自身が持つ。
3. **階層(ブラウズ可能性)は`id`文字列自体を変えず、`target`から導出するビューとして提供する**: 例えば`docs/ssot-coverage-map.md`のような自動生成物、または`target.kind`→`target.ref`でグルーピングするクエリスクリプト。Windowsレジストリの「配下を列挙できる」という利点だけを取り出し、Facts項目8で指摘した「厳密な単一親ツリーの弊害」を避ける。
4. **段階的な導入**: `meta.phase`(現在`phase-0`)は元々段階的ロールアウトを前提にした設計であり、今回の`target`追加もこれに乗せる -- 新設スキャンは`status: experimental`で始め、既存57件への`target`後付けはbackfillとして別issueで扱う(1回のPRで57件全てに手を入れると、目的([shadow gateの検出])に対して変更範囲が不釣り合いに大きくなる)。

## 実データによるtargetバックフィル検証(ultracodeワークフロー、57件全ゲート)

上記の`target`スキーマ案が絵に描いた餅でないかを確認するため、既存57件のgateすべてに対して、ワークフロー内の6バッチ(1バッチ最大10件)で実際に`target`をバックフィルする監査を行った(各バッチには`evaluating-deterministic-gate-quality`スキルのmechanism-fit test/dimension 21の要約を渡し、無理に当てはめず`ambiguous`を許容するよう明示的に指示している)。

**結果概要**: 57件中49件(86%)が高確信度(`high`)でバックフィルできた。5件が中確信度(`medium`)、3件が`ambiguous`(無理な当てはめを避けて明示的に保留)。バックフィル自体が完全に不可能だった gate は0件。

**`target.kind`の実際の分布**(1gateが複数のtarget項目を持てるため、件数はgate数ではなく項目数):

| kind | 項目数 | 代表例 |
| --- | --- | --- |
| `file-glob` | 107 | `ssot-schema-drift` → `.gitapex/ssot.json` / `.gitapex/ssot.schema.json` |
| `workflow-event` | 56 | `ssot-schema-drift` → `test.yml:pull_request` / `test.yml:push` |
| `cross-registry-consistency` | 21 | `ssot-schema-drift` → `gates[].script`パス ⇔ 実ファイル、`policy_refs[]` ⇔ `policy_sources[].id` |
| `bash-pattern` | 14 | `bash-cli-write-and-install-guard` → `gh pr create\|edit\|close\|...`、`gh api -X/--method POST\|PUT\|PATCH\|DELETE`等5パターン |
| `mcp-tool` | 10 | `pr-title-convention` → `mcp__github__create_pull_request` |
| `github-native` | 9 | (branch protection等、GitHub側の設定に紐づくもの) |

**訂正すべき点(誠実な開示)**: 「提案する設計」の項目2では、`mcp-tool`(このセッションで呼び出し可能なツール一覧という、最も機械的に列挙しやすい対象)を完全性スキャンの起点として提案していた。しかし実データでは`mcp-tool`は6種中5番目の頻度(10件)にとどまり、最頻出は`file-glob`(107件)と`workflow-event`(56件)だった。当初の起点選定根拠(「最も列挙しやすいから」)は依然として有効だが、それが「量として最も多くの書き漏れを拾える対象」であることは意味しない -- この2つは別の基準であり、混同していた。起点をどちらの基準で選ぶかは、未解決事項に追記した。

**新たな`target.kind`が必要という発見**: 4件(`provenance-disclosure`のPR本文側、`stale-retro-stub-autoclose`、`copilot-endpoint-preflight`、`metadata-outcome-lines-drift`)は、既存6種のどれにも無理なく当てはまらなかった。共通する性質は「対象の実体が、リポジトリのコミット済みソースからは決まらず、ライブなプラットフォーム状態への問い合わせ、または他所に記録された任意の per-instance ポインタ(issueの本文、secretの値、任意のファイル/コミットの組)を読んで初めて分かる」という点。これを新しい`target.kind`候補として`runtime-resolved-reference`と命名することを提案する(未解決事項に追記)。

**中確信度・ambiguousの内訳**(全8件、無理な当てはめを避けたもの):

| id | 確信度 | 理由 |
| --- | --- | --- |
| `skill-audit-disclosure` | medium | 複数の拡張適用範囲(description変更・security-relevant skill等)を持つが、正確なglobがルール文に全ては書かれていない |
| `retrospective-gate-drift-scan` | medium | GitHub Issues APIの状態とgit logを突き合わせる仕組みそのものが対象で、単一の外部ターゲットが存在しない |
| `stale-retro-stub-autoclose` | medium | 対象はラベル+本文マーカー+経過日数による動的クエリで、固定されたアーティファクト/パスではない |
| `metadata-outcome-lines-drift` | medium | sidecarのglobは特定できるが、各行が指す先(任意のファイル/コミットの組)は列挙不能 |
| `copilot-endpoint-preflight` | medium | 対象の実体がrepo secretの整形式チェックであり、ファイル/ツール呼び出し/bashパターンのいずれでもない |
| `provenance-disclosure` | ambiguous | ルール文の「PR本文」半分はGitHub APIでライブに読むテキストで、ファイルではない(既存6種のどれにも該当しない) |
| `split-fixture-coverage` | ambiguous | 供給されたルール文はissue #928以前のsplit.md散文解析を記述しているが、実装は既にsplit.json読み取りへ移行済み(ルール文自体が実装からズレている、後述) |
| `real-checkout-git-write` | ambiguous | 対象範囲はpytestの発見規則+`pyproject.toml`の`testpaths`に動的に紐づき、固定globでは正確に表現できない |

## non-gateの観点: 多層防御として無効、またはエージェントを非合理化させるブロッカー

### 発端と既存フレームワークとの関係

ご指摘は「多層防御として有効でなく、エージェントを非合理化させるブロッカーとして介在する実装をすべきでないゲート」という観点。`evaluating-deterministic-gate-quality`スキル(`SKILL.md`・`references/mechanism-fit.md`・`references/dimensions.md`を全文読了済み)には、既にこれに近い仕組みが2つある。

1. **Mechanism-fit test(3問)**: (1) gate vs no-gate(`no-gate-warranted`)、(2) gate vs infrastructure-owned deterministic control(`infrastructure-owned-control`/`repository-authored-gate`/`layered-both`/`indeterminate`、「無限の忍耐を持つ行為者が力尽くで突破できるだけの摩擦しか足さない」場合は多層防御として無効と判定)、(3) domain placement(6基準)。
2. **Dimension 21「Gate precision, audited against real firings」**: arXiv:2607.07405「Reason Less, Verify More」を引用し、実発火に対するゲートの判定精度(4ゲート構成中1件が精度5%)を監査する。

しかし、この既存フレームワークには一つの隙間がある。Dimension 21が測るのは「ブロックの判定が正しかったか」(predicate correctness)のみであり、「ブロックされた**後**にエージェントがどう振る舞うか」という下流の行動的帰結を測る軸がどこにも存在しない。これはご指摘の「エージェントを非合理化させるブロッカー」という観点と正確に一致するギャップであり、今回はこれを埋める新ディメンション案を、一次資料で裏付けた上で提示する。

### 一次資料調査(4件、全て直接fetch確認済み)

1. **Reason Less, Verify More(arXiv:2607.07405、既存dimension21の引用元を再検証)**: 論文自身が「A gate blocks a proposed violating write but does not ensure the agent recovers; post-rejection behavior is model-dependent」と明言しつつ、それ以上は踏み込んでいない。tau²-benchのtask #39では「the gate fires repeatedly but the task remains 0/5. The agent loops against the rejection rather than finding a compliant plan」という実例が1件報告されているが、体系的な測定ではなく一事例に留まる。→ ギャップの存在を裏付ける一次資料だが、解決はしていない。
2. **Tricorder(Google、ICSE 2015)**: 誤検知率に明確な閾値制度を持つ(`< 10%`で稼働、`≥ 10%`でprobation、`≥ 25%`で停止)。新規チェック採用の第一基準として「the warning should be easy to understand and the fix should be clear」を明記済み -- 設計時の基準としては既に先例がある。一方で、Objective-Cファイルを誤って対象にしていたC++リンターの誤爆1件が原因で、Objective-C開発者が「リンター結果を全て非表示にする」という全面不信に至った実例(Sec III-E)があり、これは新ディメンションが捉えようとする「誤動作していないゲートも含めて信頼を失う」という現象そのもの。
3. **Permission Denied(arXiv:2608.02670、最も直接該当する定量研究)**: 制限的なポリシー下でコーディングエージェントがブロックされた際、コストを押し上げる主な機構の97%が「workaround construction」(回避策の構築、例: ブロックされたツールチェーンをソースからリビルド)だったと定量的に報告。ただし、この論文自身も「deny messageの表現(可読性・具体的な次アクションの有無)がエージェントの回復行動に与える因果効果」は測定しておらず、生のシステムエラー(HTTP 403、EROFS、EPERM)のみを刺激として扱っている -- ご指摘の観点がまだ専用の統制実験を持たない、という誠実なネガティブファインディング。加えて、Ona社のエンジニアリングブログには、denylistのみで代替案を提示しないゲートに対しClaude Codeが実際にパスベースの迂回を発見し、次の層(bubblewrap sandbox)にブロックされると今度は「sandbox自体を無効化しよう」と自発的に推論した、実トランスクリプトの実例が記録されている。AC4A論文(arXiv:2603.20933)は拒否時のハンドリングをAsk/Skip/Infer/YOLOの4分類で扱っており、「拒否後に合理的な代替パスを提示するか」を設計上の独立した軸として既に業界が意識している傍証となる。
4. **Bruce Schneier「Beyond Security Theater」+ 関連一次資料**: security theaterの定義(「なぜリスクを下げるのかという因果の連鎖を誰も説明できない対策」)は、mechanism-fitとは別の切り口の判定基準を与える。NRC Regulatory Guide 1.174のdefense-in-depth基準その2「構造的な弱点を補うために手続き的・プログラム的活動に過度に依存しない」は、`infrastructure-owned-control`判定の公式な先例。Knight & Leveson(1986)の実験は、独立に開発された冗長実装同士でも99%の信頼度で「独立に故障する」という仮定が棄却されたことを示しており、同じ難しい問題に対しては独立実装でも同じ間違いを犯す(=見かけ上layeredでも実は共通モード故障)というメカニズムを与える。

(補足として、Parasuraman & Riley(1997)の「cry wolf effect」「creative disablement」という確立した学術用語、Google SREブックの「この警報はいつか無視できるようになると分かっているか」という設計時チェックリスト、Chou(2005)の「開発者は誤検知を修正も活用もせず放置する」という報告も、同じ現象の裏付けとして得られている。)

### 提案: 新ディメンション「Deny-path recoverability(post-block agent behavior)」

`evaluating-deterministic-gate-quality`スキルの既存ルーブリック(9ディメンション)への追加案として、以下を提示する(このスキル本体への実装は本記録のスコープ外、次の未解決事項参照)。

**定義**: ブロックの判定が正しかったかどうかを問わず(真のブロックであっても)、ブロックされた**後**にエージェントに何が起きるかを監査するディメンション。2部構成。

- **Part A(設計時チェック)**: 各ゲートの実際のdeny/rejectメッセージについて、(1)具体的な理由を述べているか(単なるpass/fail、生のシステムエラーコードだけではないか)、(2)ゲートが認める具体的な次アクションを最低1つ名指ししているか、(3)どの分岐を辿っても到達可能な準拠パスが存在するか(行き止まりが「creative disablement」やOna事例の迂回試行を誘発する)、(4)fail-closed分岐については「一時的な障害だから待て/エスカレートせよ」と「あなたの操作が誤っているから別の方法で再試行せよ」を区別しているか。
- **Part B(監査時チェック、実発火ログがある場合)**: 実際の発火をcompliant recovery / timeout-grind / workaround-construction / learned-bypass / task-abandonmentに分類し、比率を追跡する(dimension 21の「実発火に対する監査」という設計をそのまま踏襲)。
- **判定トークン案**: `actionable-recovery`(両パート通過)/ `dead-end-risk`(Part Aで行き止まり分岐が見つかる)/ `escalation-risk`(Part Bでworkaround-construction/learned-bypassの証拠)/ `indeterminate`(発火履歴なし)。

**Dimension 21との違い**: Dimension 21はブロックの述語が正しかったか(判定の正しさ)を、正解軌跡との突き合わせで機械的に測る。新ディメンションはブロックの帰結(エージェントの行動)を測り、判定の正しさとは独立した軸である -- 完璧な精度(100%正しいブロック)を持つゲートでも、素っ気ないメッセージがリトライループを誘発すればこのディメンションでは低評価になり得る一方、非ゼロの誤検知率を公然と開示していても安価な waiver 経路が用意されていれば(gitapexの`exception-handler-gap`・`provenance-disclosure`がその実例)このディメンションでは良好となり得る。

**`infrastructure-owned-control`との違い**: 後者は「このゲートはそもそも存在すべきか」を問う一回限りの判定。新ディメンションは「このゲートは存在すべきだと分かった上で、その失敗時UXはエージェントにとって安全か」を問う、独立した軸。実際に監査全体で4象限すべてに実例があった: `pr-upstream-pushed`は`infrastructure-owned-control`(GitHubのcreate-PR検証と重複)でありながらdenyメッセージは良質(redundant-but-safe)。`behind-base`は明確に`gate-warranted`でありながらexit-2分岐に設計された回避経路が無く、`--no-verify`という他の全pre-push hookを無効化する強行策へエージェントを押しやりかねない(warranted-but-unsafe)。両軸を混同すると、正当なゲートの悪いUXを「削除の根拠」と誤読したり、冗長なゲートの良いUXを「存続の十分条件」と誤読したりする。

### non-gate候補として浮上した12件

以下は、既存のmechanism-fit(4件)、または新ディメンション(8件)のいずれかに抵触すると監査で判定された gate。**いずれもゲートの削除・無効化・弱体化の根拠ではなく、人間が判断すべき所見として提示するのみ**(CLAUDE.md第4節の安全境界、および統合エージェント自身が明示した注記)。

| id | 抵触する観点 | 要旨 |
| --- | --- | --- |
| `pr-upstream-pushed` | mechanism-fit(`infrastructure-owned-control`) | フック自身のコメントが「GitHubのcreate_pull_request呼び出しが既に同じ入力を検証しており、fail-openしても自前のエラーがGitHubの生エラーに置き換わるだけ」と認めている |
| `behind-base` | 新ディメンション(未設計のexit-2分岐) | 「信頼できない」exit-2分岐に意図的な回避手段が無いとスクリプト自身のdocstringが認めており、オフライン等で遭遇したエージェントを`--no-verify`という他の全pre-push hookを無効化する強行策へ押しやりかねない(exit-1の本来のFAIL分岐は良設計) |
| `skill-rename-lifecycle` | 新ディメンション(行き止まり) | PR全体の集計(削除数>0かつ追加数>0)のみで判定し、1対1の対応付けをしないため、FAILメッセージが促す「意図的な削除だと確認せよ」に対する具体的な確認手段が存在しない -- 結果としてPR分割か偽の`renamedFrom`捏造しか残らない |
| `skill-branch-fixture-coverage` | 新ディメンション(既知の誤検知を隠すメッセージ) | スクリプト自身が過剰カウントの可能性を認めているが、FAILメッセージはそれを開示せず、エージェントを不要なfixture量産へ誘導しうる |
| `split-fixture-coverage` | 新ディメンション(復旧先の誤誘導) | レジストリのルール文がissue #928以前のsplit.md散文解析を記述したまま古くなっており、実装は既にsplit.json読み取りへ移行済み -- レジストリを見て学んだ対応先が実際には検査されない |
| `transfer-check-disclosure` | 新ディメンション(無告知のスコープ拡大) | ルール文は差分限定の旧版を記述するが、実装は全ファイル監査に拡大済み -- 既存エントリは対象外という誤解を招きやすい |
| `pr-issue-acm-disclosure` | 新ディメンション(一時障害メッセージの弱さ、ソフトな要観察) | 一時的な5xxでも「could not fetch issue (error)」としか示されず、「一時的だから待て」という枠組みが無い -- tau²-bench task #39と同型のタイトループを誘発しうる可能性(監査自身は確度を落として報告) |
| `waza-eval-gate` | mechanism-fit(結果に強制力がない) | ルール文自身が「not yet a required status check」と明記 |
| `workflow-lint` | mechanism-fit(結果に強制力がない) | ヘッダーコメントが「promotion予定、未実施」と明記 |
| `python-lint` | mechanism-fit(結果に強制力がない) | 同上(同一ヘッダーコメントを共有) |
| `bare-python3-invocation` | mechanism-fit(結果に強制力がない) | `.github/rulesets/main.json`のrequired_status_checksに未登録と直接確認 |
| `stdlib-only-claim-drift` | mechanism-fit(結果に強制力がない) | 同上、必須チェック昇格候補の体裁を持ちながら未登録 |

推奨される次のアクションは是正の種類ごとに異なる: メッセージ/回避経路の再設計(`skill-rename-lifecycle`・`skill-branch-fixture-coverage`・`behind-base`・`pr-issue-acm-disclosure`)、レジストリのルール文修正(`split-fixture-coverage`・`transfer-check-disclosure`)、required status check昇格の検討(mechanism-fit側5件 + 統合検討としての`pr-upstream-pushed`)であり、いずれも「削除」ではない。

なお、監査は`skill-eval-status-doc-drift`・`exception-handler-gap`・`hidden-characters`・`routine-scope-enforcement`・`real-checkout-git-write`・`provenance-disclosure`(是正済みの自己発火履歴を含む)を、良好なfriction設計の模範例として肯定的に挙げている -- 上記12件の是正時の参考にできる。

**総括**: 57件中45件(79%)は今回の監査でmechanism-fit・新ディメンションいずれの兆候も見られなかった。12件(21%)が人間の判断を要する所見として浮上した。

## 図: 現状(平坦・不可視)と提案(ファセット化・可視)の比較

> 元のArtifactではこの節は左右2枚のSVG比較図だったが、この変換スクリプトは`<svg>`/`<figure>`を扱わないため図そのものは失われた。以下は図の実データ(ラベル・テーブル内容)をMarkdownとして忠実に再構成したもの(創作的な再解釈ではない)。同じ内容の要約はFacts項目5・6にも散文で既出。

**現状: 平坦なidリスト**

```
bash-cli-write-and-install-guard
pr-title-convention
skill-audit-disclosure
pr-upstream-pushed
... (57件、アルファベット順)
```

共通の座標系なし、目的で命名された文字列の羅列。

`mcp__github__merge_pull_request`は? → この57件を読むだけでは分からない → コードベース全体をgrepして初めて発見(shadow gate)。

**提案: targetファセットによる被覆表(自動生成)**

mcp-toolターゲット × 登録ゲート:

| mcp-toolターゲット | 状態 |
| --- | --- |
| `create_pull_request` | 登録済み |
| `update_pull_request` | 登録済み |
| `issue_write` | 登録済み |
| `merge_pull_request` | shadow gate |
| `enable_pr_auto_merge` | 未監査 |
| `create_or_update_file` | 未監査 |

実行可能なツール一覧から機械的に列挙、表自体が自動生成される。「shadow gate」と「未監査」を区別 -- 後者は安全性未判定であることが可視化される。

現状(上)はgate idの平坦なリストで、特定のツールを対象とする項目の有無はコードベースを直接探索しない限り分からない。提案(下)は実行可能なツール一覧を行、登録有無を列とする被覆表を自動生成し、`merge_pull_request`のような既知の欠落(shadow gate)と`enable_pr_auto_merge`のような未監査の対象を、表そのものから直接見分けられるようにする。

## メタデータ成熟度: 弱みを克服する修正案(4件、`target`案と合わせて計5件)

前段のレビュー(セキュア開発の文脈でのスキーマ成熟度評価)で見つかった4つの弱み -- fail-open/fail-closedの未構造化、既知のbypass・深刻度の未構造化、`security-control-inventory.md`との非連結、測定結果を書き戻す場所の不在 -- それぞれに対する具体的な修正案。`target`フィールド(前述)と合わせて計5件の新設フィールド提案になるため、末尾で導入順序をまとめて示す。

**事実系(fact)と検証系(review verdict)の区別**: 5件のうち`target`・`fail_mode`・`known_bypasses`・`blast_radius`・`threat_refs`は、コードを読めば一意に決まる**事実**であり、`kind`や`planes`と同じ性格を持つ。一方`review`オブジェクトは、人間またはスキルによる**判断の記録**であり、時間とともに陳腐化しうる(いつ・誰が・何を根拠に判断したかを伴う必要がある)。この区別を曖昧にすると、"いつの情報か分からない事実"と"誰も確認していない判断"が同じ扱いになり、かえってレジストリの信頼性を下げる。

### 1. `fail_mode` -- fail-open/fail-closedの構造化

```
"fail_mode": {
  "type": "object",
  "additionalProperties": false,
  "required": ["on_error", "rationale"],
  "properties": {
    "on_error": {"enum": ["fail-open", "fail-closed", "mixed"]},
    "rationale": {"type": "string", "minLength": 1}
  }
}
```

現状、この最重要のセキュリティ性質は`rule`の自由文に埋もれている(例: `pr-upstream-pushed`「fails open on any unresolvable local git state」、`behind-base`「exit 2, ... never falls back to comparing against a possibly-stale local ref」)。`mixed`は分岐ごとに挙動が異なるゲート用(`rationale`にどの分岐がどちらかを記す)。`evaluating-deterministic-gate-quality`のdimension 15(Fail-closed default on incomplete or malformed input)が既にレビュー時にこの性質を評価しているため、新設は「そのレビュー結果を書ける場所を作る」に近い。

### 2. `known_bypasses` + `blast_radius` -- 既知の回避手段と深刻度の構造化

```
"bypass_review_status": {"enum": ["reviewed-none-found", "reviewed-found-listed-below", "not-yet-reviewed"]},
"known_bypasses": {
  "type": "array",
  "items": {
    "type": "object",
    "additionalProperties": false,
    "required": ["description", "severity"],
    "properties": {
      "description": {"type": "string", "minLength": 1},
      "severity": {"enum": ["low", "medium", "high", "critical"]},
      "tracking_issue": {"type": ["integer", "null"], "minimum": 1}
    }
  }
},
"blast_radius": {"enum": ["local-workspace", "repository", "organization", "external-third-party"]}
```

`evaluating-deterministic-gate-quality`のdimension 9(Known-limitation disclosure)は既に回避手段の自己開示を要求しているが(例: `bash-cli-write-and-install-guard`の「base64パイプでshに渡す回避はどんな正規表現ゲートの手も届かない」という自己開示)、開示先はdocstringの自由文のみ。`known_bypasses`が空配列であることと「まだ確認していない」ことを区別できないと、`policy_refs`のような正当な空配列(未確認ではなく該当なし)と混同されるため、`bypass_review_status`を必須の姉妹フィールドとして分離する(`local_invocation`/`local_exclusion`の"沈黙を許さない"設計をそのまま踏襲)。`blast_radius`はCLAUDE.md第4節が既に使っている語彙をそのままレジストリに持ち込むもので、新しい概念の導入ではない。

### 3. `threat_refs` -- `docs/security-control-inventory.md`との構造的連結

```
"threat_refs": {
  "type": "array",
  "items": {"type": "string", "pattern": "^(ASI|LLM)\\d{2}$"}
}
```

現状の連結は、`security-control-inventory.md`のRationale文中に書かれたファイルパス(例: `hooks/check-bash-safety.sh`)が`bash-cli-write-and-install-guard`の`script`値と偶然一致する、という人間が読んで気づく水準に留まる。`owasp-asi-mapping-completeness`/`owasp-llm-mapping-completeness`ゲートのルール文を直接確認したが、両者とも「ASI01-10各1行・status列挙値・rationale接頭辞」という構造の完全性のみを検査し、引用されたパスや issue番号の実在性は検査しない。

修正は両側が必要: (a) `ssot.json`側に`threat_refs`を追加、(b) `security-control-inventory.md`側は新しい列を追加せず(ヘッダー行regexが固定3列を前提にしており、`[deny]`等のタグを新列でなくRationateセル内にインライン化した先例と同じ制約)、Rationaleセル内にgate idをインラインコード(``bash-cli-write-and-install-guard``)で引用する既存の"タグをセル内に埋め込む"慣習を踏襲する。検査は`registry-wiring-scan`ゲート(`.github/scripts/*.py`の`cli_flag`registryとworkflowファイルの双方向突き合わせ、issue #797で逆方向を追加した先例)と同じ設計パターンを一般化し、`ssot.json`の`threat_refs`→`security-control-inventory.md`の実在確認、および逆方向(Rationale内のgate id引用→`ssot.json`に実在するか)の両方向を検査する新規ゲートとして実装する。

### 4. `review`オブジェクト -- 測定結果の永続化(検証系、事実系と分離)

```
"review": {
  "type": "object",
  "additionalProperties": false,
  "required": ["last_reviewed", "mechanism_fit_verdict"],
  "properties": {
    "last_reviewed": {"type": "string", "format": "date"},
    "reviewing_pr": {"type": ["integer", "null"], "minimum": 1},
    "mechanism_fit_verdict": {"enum": ["gate-warranted", "no-gate-warranted", "infrastructure-owned-control", "layered-both", "indeterminate"]},
    "dimension_21_precision": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "true_blocks": {"type": "integer", "minimum": 0},
        "false_blocks": {"type": "integer", "minimum": 0},
        "sample_source": {"type": "string", "minLength": 1}
      }
    },
    "dimension_24_deny_path_verdict": {"enum": ["actionable-recovery", "dead-end-risk", "escalation-risk", "indeterminate"]}
  }
}
```

今回のセッション自体がこの欠落の実例: dimension 21の精度監査、mechanism-fit判定、dimension 24のverdict tokenは、いずれも一度きりのレビュー出力として生成され、`ssot.json`のどこにも永続化されない。フィールド自体は任意(`review`が無い = 未レビュー、これも意味のある状態)とし、存在する場合のみ`last_reviewed`必須とする。陳腐化を防ぐため、`retrospective-gate-drift-scan`(閾値+日次cronで自動検知する既存の先例)と同じ設計で、`last_reviewed`が一定期間より古いゲートを検知する常設ゲートを併設する。**このフィールドはissue #1229でdimension 24の語彙が確定してから着手すべき**(語彙が固まる前に器を作ると、確定後に`review`スキーマ自体の再改訂が発生する)。

## 一覧: 5件の新設フィールドと導入順序の提案

| フィールド | 分類 | 埋める弱み | 依存 | 提案する導入順序 |
| --- | --- | --- | --- | --- |
| `fail_mode` | 事実 | fail-open/closedの未構造化 | なし | 1(最も安価、判断要素が少ない) |
| `target` | 事実 | `trigger`の未構造化(前述) | なし | 2(既存の未解決事項、設計済み) |
| `known_bypasses` + `bypass_review_status` + `blast_radius` | 事実 | bypass・深刻度の未構造化 | dimension 9のレビュー結果があると精度が上がる | 3 |
| `threat_refs` | 事実 | `security-control-inventory.md`との非連結 | `security-control-inventory.md`側の記法変更も同時に必要 | 4(両側変更のため調整コストが最も高い) |
| `review` | 検証 | 測定結果を書き戻す場所の不在 | issue #1229のdimension 24語彙確定を待つ | 5(最後、他の全てが検証対象を提供し終えてから) |

導入順序の根拠は、以前に明文化した「安価・低リスクな確認を先に、依存のあるものを後に」という原則(段階の並び順の原則、`reviewing-a-pull-request-design.md`参照)をそのまま踏襲している。各フィールドは`ssot.schema.json`自身の既定通り`schema_version`のバンプを要し、CLAUDE.md第3節の規定により、新設と同じ変更でそのフィールドの完全性を検査するゲート(バックフィル対象の欠落を検知する、`target`提案時と同じロールアウト方式)を併せて出荷する。既存57件への一括バックフィルは行わず、新規ゲート追加分から義務化し、既存分は段階的に埋める。

**追記(依頼者の判断: スキーマだけを先に追加)**: 網羅性ゲート・データバックフィルを本体から切り離し、issue化した。

- **issue #1231**: `fail_mode`・`target`・`bypass_review_status`の3フィールドをスキーマに追加。`bypass_review_status`のみ、判断不要・機械的なため既存57件へ`"not-yet-reviewed"`の一括backfillも同時に行う。`fail_mode`・`target`はスキーマ形状のみで、データ投入は一切行わない(`target`は49件分の高確信度backfillが既に手元にあるが、あえてこのissueには含めない)。
- **issue #1232**(#1231のfollow-up、`Non-goals`の開示に対応する実体): `target`の49件backfillの実データ投入、残り8件の人的判断、`bypass_review_status`の`required`昇格、`fail_mode`/`target`の非block式カバレッジ報告ゲートの新設。

CLAUDE.md第3節との緊張(「不変条件は同じ変更でドリフトゲートを出荷する」)は、沈黙の先送りではなく開示付きの先送りとして解消した -- 既存の`local_exclusion`(沈黙を許さない設計)と同じパターンを、issue単位に拡張した形になる。`known_bypasses`本体・`blast_radius`・`threat_refs`・`review`は、この2issueのいずれにも含まれず、引き続き未着手。

## 未解決事項

1. **完全性スキャンの起点とする`target.kind`(実データを踏まえ改訂)**: 当初`mcp-tool`を「最も列挙しやすいから」起点としたが、実データでは`file-glob`(107件)・`workflow-event`(56件)が最頻出で、`mcp-tool`は10件と少数派だった。「列挙しやすさ」と「量的なカバレッジ」は別基準であり、どちらを優先して完全性スキャンの第一弾とするかは未決定。また、新たに提案する`runtime-resolved-reference`(4件の実例で必要性を確認)を`target.kind`の列挙に正式に加えるかどうかも未決定。
2. **既存57件への`target`後付け(backfill)の進め方**: 今回のワークフローで49件(86%)分は高確信度のバックフィル案が既に手元にある。残り8件(medium 5 + ambiguous 3、うち`split-fixture-coverage`はレジストリのルール文自体が実装から乖離していることも判明)は個別の人的判断を要する。49件を先行して1回のPRに反映し8件を別issueで扱うか、全件を1回でまとめるかは未決定。
3. **本記録をissue化するか**: `.gitapex/ssot.json`の founding issue(#123)の下に追加のトラッキングissueを作るか、それとも#123自身の後続フェーズとして扱うか。
4. **(解決済み)新ディメンション「Deny-path recoverability」の`evaluating-deterministic-gate-quality`スキル本体への正式追加**: issue化。[https://github.com/tvna/gitapex/issues/1229](https://github.com/tvna/gitapex/issues/1229) -- ただし起票の過程で本記録自体の誤りが2件見つかったため訂正する。(a) `references/dimensions.md`を直接読んだところ、ディメンション22・23は既に他の目的(集計結果の発火/非発火層別化、呼び出し元環境の成熟度)で使用済みだったため、新ディメンションの正しい番号は**24**(23の直後に追記、番号の割り込みによる連鎖的な繰り下げを避ける)。(b) `skill-quality-rubric-vocabulary-drift`ゲートは`evaluating-skill-quality`の`references/rubric.md`専用(見出し形式`## N. <Name>`を対象)であり、`dimensions.md`(番号付きリスト項目`N. **Name.**`)の自己整合性は現状どのゲートも守っていないことを確認した -- 「自動的に効く」という前段の記述は誤りだった。issue #1229にはこのドリフトゲートの新設と、確定文言による57件の正式な再監査を、依頼者の判断でスコープに含めている。
5. **12件のnon-gate候補への対応方針**: 一括是正issue、gateごとの個別issue、または当面は経過観察のみとして記録に留めるか、未決定(issue #1229のNon-goalsとして明示的にスコープ外とした)。
6. **(部分的に解決済み)`fail_mode`・`known_bypasses`/`blast_radius`・`threat_refs`・`review`の4件をissue化するか**: `fail_mode`・`target`(スキーマのみ)・`bypass_review_status`(スキーマ+全件backfill)は issue #1231 として起票済み。データバックフィル・網羅性ゲート・`required`昇格はfollow-upの issue #1232 として分離起票済み。残る`known_bypasses`本体・`blast_radius`・`threat_refs`・`review`は未着手のまま。`threat_refs`は`security-control-inventory.md`側の記法変更も伴うため単独issue化を推奨する方針は維持。`review`はissue #1229のdimension 24語彙確定を待つ。

## 次のステップ

Design-only。上記未解決事項についてご判断を仰ぐ。ご依頼があれば、次のいずれか(または複数)から着手できる: (a)`target`フィールドのスキーマ変更(schema_versionバンプ)と、バックフィル済み49件分の反映を実装issueとして起票、(b)完全性スキャンの新規gate追加、(c)新ディメンションの`evaluating-deterministic-gate-quality`スキル本体への追加提案、(d)12件のnon-gate候補のうち是正方針が明確なもの(`skill-rename-lifecycle`のメッセージ再設計等)から個別issue化、(e)`fail_mode`(導入順序1番、最も着手コストが低い)から順にissue化。
