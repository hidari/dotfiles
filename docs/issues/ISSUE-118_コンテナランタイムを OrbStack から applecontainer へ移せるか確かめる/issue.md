---
status: open
---

# chore: コンテナランタイムを OrbStack から apple/container へ移せるか確かめる

## 背景

起票した時点 (2026-10-10) では、開発機のコンテナランタイムは OrbStack で、`/usr/local/bin/docker` は OrbStack.app 内の docker への symlink になっていた。apple/container も pkg インストーラで入っていたが、版は1.0.0のまま止まっていた。どちらも Brewfile の外にあった。その後 container は brew 版へ寄せて Brewfile に載せた (「進め方の方針」節)。

以前 apple/container へ寄せようとしたときは `docker compose` に相当するものが無く、compose 互換のツールを別リポジトリで自作して試した。その後の状況を2026-10-10時点で調べ直した結果が下の節にある。そのあと Docker.app と OrbStack は外す方針に決めたが、外すのは試して動いてからで、移行の可否はまだ確かめている途中である。

## 調査結果 (2026-10-10時点のスナップショット)

数値と版は動くので、着手時に引き直すこと。

### upstream の方針

- apple/container の最新は1.5.0 (2026-09-29)。1.0.0からの間に compose 相当は入っていない
- compose は本体に入れず外部プラグインとして作る、という方針が明言されている。compose 実装の PR (apple/container#239) は2026-04に、Docker Engine と compose を同梱する PR (apple/container#2123) は2026-08-28に、maintainer がその理由でクローズした
- Docker Engine API (docker.sock 相当) を本体で提供する予定も無い (apple/container#66 は not_planned)
- 1.2.0で k8s プラグインが入ったが、Kubernetes クラスタを立てる仕組みで compose ファイルは読まない。experimental で、ホストへのポート公開も無い

### compose 相当の選択肢

- 試す価値あり (最有力): socktainer/socktainer と素の `docker compose` の組み合わせ
  - Docker Engine API を apple/container へ橋渡しするシムで、docker CLI と compose がそのまま使える
  - v1.5.2 (2026-10-09) で、ほぼ毎週リリースされている。compose 対応の PR (socktainer/socktainer#212) はマージ済み
  - apple/container 1.5.0と macOS 26が要件。homebrew-core に formula がある
- 試す価値あり (次点): Mcrich23/Container-Compose
  - compose ファイルを読んで `container` を駆動する。maintainer が名指しした外部実装
  - 1.2.0 (2026-09-21)。homebrew-core に formula がある
  - README は自ら「(limited)」と書いており、extends / include / build context / 補間などが未対応のまま open
- 補助としてなら: andrew-waters/orchard
  - GUI で、compose.yaml を依存順に起動・停止できる。v2.5.1 (2026-10-05)
- まだ早い: andrew-waters/compose、stephenlclarke/container-compose、us/mocker など
  - どれも作られたばかりか0.x、または特定の版専用

OrbStack は apple/container をバックエンドにする予定は無いと明言している。Lima と Colima も取り込んでいない。

### 本体に欠けたままの機能

1.0.0と1.5.0のソースを比べた結果、自作したときに外側で埋める必要があった機能は、どれも1.5.0でも埋まっていない。

- カスタムネットワーク上でサービス名による名前解決ができない (apple/container#1809)
- `--restart` 相当が無い (apple/container#2142)
- `--add-host` 相当が無い
- コンテナの healthcheck が無い
- メモリの下限が200MiB

socktainer はネットワークごとに CoreDNS サイドカーを置いて名前解決を埋めている。restart は socktainer のプロセスが生きている間しか効かず、`network connect` は受け付けるだけで何もしない。

### compose 以外の移行障害

- bind mount (virtio-fs) ではホスト側の変更がゲストの inotify に届かない (apple/container#141、open)。ファイル監視やホットリロードに頼る開発ワークフローが動かない
- ゲストで解放したメモリがホストへ返らない (本体の docs/technical-overview.md)。コンテナごとに VM が立つので、常駐するサービスが多いほど OrbStack より不利になりうる
- x86_64 イメージは Rosetta 経由で動くが、Rosetta 下の不具合が複数 open のまま
- Testcontainers も devcontainer も公式には非対応。socktainer 経由で動いたという利用者の報告があるだけ

## 進め方の方針

Docker.app と OrbStack は外す (2026-10-10にユーザーが決定)。OrbStack は安定しているが、マシンのリソースを大きく占有するのが理由。

- compose のスタックは Container-Compose で試す。足りない部分は自作の compose 互換ツールを進める選択肢も残す
- Supabase CLI のように Docker Engine API を直接叩くツールは Container-Compose では置き換えられないので、socktainer で試す
- container は brew へ寄せて Brewfile で管理する。pkg 版は `uninstall-container.sh -k` でデータを残して外した
- 外すのは試して動いてから。それまで OrbStack と併存させる。試用中は `DOCKER_HOST` の export と `docker context use` をしない (並行して動く作業の docker が OrbStack から切り替わってしまうため)。socktainer を使うときはコマンドごとに `--context` で指す
- Container-Compose は、小さな自作の例、自作ツールの合成の例、実プロジェクトの testing スタックの順に試す

## 試用結果 (2026-10-10、container 1.5.0 / Container-Compose 1.2.0)

1.0.0時代のイメージは、pkg 版を `-k` で外して brew 版を入れたあとも引き継がれた。

- DNS ドメインが未登録だと、サービス名の解決は起動後に exec で `/etc/hosts` を書き換える方式になる。すぐ終わるジョブはコマンドが先に走るので名前を引けない (常駐するサービスでは書き換えが間に合う)。`sudo container system dns create <プロジェクト名>` で登録すると解決できた。プロジェクトごとに sudo が要る
- `depends_on` の `service_completed_successfully` がジョブの完了を待たない。`true` だけのジョブは通るが、`sleep 3` のジョブは実行中のまま「成功して終わっていない」と判定され、`up` が rc 1で止まる
- `up` が rc 1で止まっても、それまでに起動したサービスは動いたまま残る
- `down` はコンテナを止めるだけで削除しない。次の `up` は作り直すので実害は小さい
- `networks.default.name` を書くとネットワークは作るが、サービスはそこへ繋がず `default` に載る。apple/container のカスタムネットワークでは名前を引けない (apple/container#1809) ので、結果的には動く
- healthcheck の `service_healthy` 待ち、ポート公開、build と build args は期待どおりに動いた
- `ps` と `logs` のサブコマンドは無い。`container` を直接使う

実プロジェクトの testing スタックは、静的に読んだ時点で次の障害が見えたので、まだ試していない。

- 同じスタックが OrbStack 側で動いており、ホスト側のポートが埋まっている。試すにはそちらを止める必要がある
- `service_completed_successfully` で初期化ジョブを待つ構成なので、上の不具合を踏む
- `extends` で別ファイルのサービスを引き込んでいる (Container-Compose では未対応のまま open)
- `host.docker.internal` でホストの Supabase へ繋いでいる。apple/container には相当する名前が無い

## 受け箱から届いた関連情報 (2026-10-22)

他のリポジトリのセッションから届いた報告で、報告者は公式のドキュメントと上流の Issue を読んだだけで、動かしてはいない (ドキュメントのみ)。dotfiles でも確かめていない。上の方針の「Supabase CLI は Docker Engine API を直接叩くので socktainer で試す」の前提に触る。

- Supabase CLI には実験的な stack 機能があり、Docker を使わずにローカルで動くネイティブのランタイムを持つ
- `--runtime` を省くと Docker、Podman、native の順に最初に応答したものを使う。Docker が動いているマシンでは `stack = true` を足しただけではネイティブにならない
- Auth のメールテンプレートを `content_path` で指定する設定があると、stack モードはネイティブでも Docker のランタイムでも起動を拒否する。テンプレートを `content` に直接書く回避も弾かれる (上流の supabase/cli#7200、未修正)。カスタムのメールテンプレートを使うプロジェクトでは、stack モード自体がまだ使えない

報告者の提案は、ネイティブのランタイムを検討するときは先に `content_path` の有無を grep すること。

## タスク

- [x] container の入手経路を決める (pkg のままか brew へ寄せるか)。brew へ寄せるなら Brewfile に載せる (ISSUE-95 の射程の議論と合わせる)
- [x] container を1.5.0へ上げる。上げる前に、既存のイメージとボリュームが引き継がれるかを確かめる
- [ ] OrbStack と同時に動かしたときに、ポート・サブネット・DNS が衝突しないかを確かめる
- [ ] socktainer と素の `docker compose` で、実際に使う compose ファイルを起動できるか確かめる
- [ ] Container-Compose 1.2.0でも同じ compose ファイルを試し、socktainer と比べる (小さな例と合成の例は試した。結果は上の節)
- [ ] Container-Compose で見つけた不具合を upstream へ報告するか、自作ツールで埋めるかを決める
- [ ] 移行障害を実測する: inotify が届かないことの影響、多数のサービスを常駐させたときのメモリ、使っているイメージが arm64 で動くか
- [ ] 移行するかを決め、決めた結果を `home/.claude/references/host-environment.md` の隔離先コンテナの記述へ反映する
- [ ] 移行するなら、OrbStack.app と Docker.app、`/usr/local/bin/docker` の symlink、docker context の扱いを決める
- [ ] 自作した compose 互換ツールを畳むか続けるかを、そのリポジトリ側の Issue で決める
- [ ] 実際に使うプロジェクトの Supabase の設定に `content_path` があるかを grep し、無ければ Supabase CLI のネイティブのランタイムで起動できるか確かめる。起動できるなら、socktainer で試す対象から Supabase CLI を外す

## 関連

- ISSUE-95 (Brewfile の射程が実機とずれている。OrbStack は Brewfile の外にある)
- ISSUE-127 (監査用の砂箱イメージ)。こちらが先行する。根拠は ISSUE-46 の順序制約表が持つ
- apple/container#239、apple/container#2123 (compose を本体に入れない方針)
- apple/container#66 (Docker Engine API を提供しない)
- apple/container#141、apple/container#1809、apple/container#2142 (本体に欠けたままの機能)
- socktainer/socktainer#212 (compose 対応)、socktainer/socktainer#392 (formula の依存で container が重複する)
- supabase/cli#7200 (stack モードが `content_path` のメールテンプレートで起動を拒否する)
- ISSUE-134: 同じ報告のうち、CI で Supabase を立てる費用についての報告者の提案を持つ
