---
status: open
---

# refactor: cloudflare の security-audit skill を試用し重複する自作 skill を寄せる

## 背景

cloudflare/security-audit-skill の `security-audit` を apm で user スコープへ入れた (pin は `home/apm.yml`)。しばらく実際のリポジトリで使い、良ければ自作の security-blue-red-team の重複する部分をこちらへ寄せる。寄せる側の canonical は agentic-coding-tools なので、整理そのものは agentic-coding-tools への委譲になる。dotfiles で行うのは試用の記録と、寄せたあとの pin の更新まで。

### 導入時に読んだ既定の挙動 (pin した上流のコミットは2026-09-14のもので、2026-10-07に確認した時点の main 先頭)

こちらの運用と合わない既定が2つある。試用ではこれを手当てしながら回す。

- full audit の出力先の既定がホーム直下の新規ディレクトリ (`SKILL.md` の Full audit setup)。リポジトリ内で回すなら ignore 済みの `.cache/` 配下を明示して渡す
- recon・hunter・verifier を上限なしで並列に起動する。上限は予算 (budget) を指定したときだけ掛かり、既定は null。並列の本数を事前に告げて確かめる運用と衝突するので、回すときは予算を指定する

プロンプトインジェクション・隠し文字・外部通信は見つからなかった。同梱の検証スクリプト (.cjs) は引数のファイルと同梱の schema だけを読み、書き込みも子プロセスの起動もしない。

### 重複の見取り図 (導入時のスナップショット)

主に重なるのは security-blue-red-team だけで、他の自作 skill はキーワードが偶然当たっただけだった。

- red-team の Layer 1 (静的) と Layer 4 (高リスクの静的): 部分的に重複。上流は recon・カバレッジ台帳・独立検証まで持つ。寄せる第一候補
- red-team の Layer 2 / 3 (staging への受動・能動 HTTP): 衝突。上流はデプロイ済みの対象への送信を禁じる。自作に残す
- findings.json の契約 (severity の段階・fingerprint・判定): 衝突。同名のファイルで schema が噛み合わない。寄せる前にどちらかへ統一するか変換を挟む
- 出力先 (`docs/security-reviews/<日付>/`): 衝突。上流は対象の外か ignore 済みのディレクトリだけを許す。寄せるなら上流の規則に合わせる
- ヘッダ・Cookie のチェックリスト指摘: 衝突。上流はフラグの欠落だけでは脆弱性と数えない。上流の基準に寄せる
- blue-team Mode B の静的監査 (認証認可・入力検証・RLS): 部分的に重複。ログのカバレッジは上流に無い。静的な部分は寄せ、ログは残す
- blue-team Mode A (優先度と工数のトリアージ): 補完。上流は改善計画を作らない。残すが、上流の出力を読むなら変換が要る
- 本番ゲート・allow_targets・送信量の上限: 補完。上流はローカル実行の隔離だけを守る。残す
- security-cleanup・security-profile: 重複なし。残す

## タスク

- [ ] 実際のリポジトリで guidance mode を数回使い、指摘の質と誤検知を記録する
- [ ] full audit を予算付き・出力先 `.cache/` 指定で1回回し、所要と指摘を記録する
- [ ] 採否を決める (Hidari の判断)
- [ ] 採るなら、寄せる範囲と findings.json の扱いを決めて agentic-coding-tools へ委譲する
- [ ] 寄せたあとの pin を dotfiles の `home/apm.yml` で更新する

## 関連

- ISSUE-40: security-blue-red-team の command と agent が二重に登録されている件。寄せるときに一緒に片付く可能性がある
