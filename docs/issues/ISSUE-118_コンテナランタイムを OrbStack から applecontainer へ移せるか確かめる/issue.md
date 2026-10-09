---
status: open
---

# chore: コンテナランタイムを OrbStack から apple/container へ移せるか確かめる

## 背景

開発機のコンテナランタイムは OrbStack で、`/usr/local/bin/docker` は OrbStack.app 内の docker への symlink になっている。apple/container も pkg インストーラで入っているが、版は1.0.0のまま止まっている。どちらも Brewfile の外にある。

以前 apple/container へ寄せようとしたときは `docker compose` に相当するものが無く、compose 互換のツールを別リポジトリで自作して試した。その後の状況を2026-10-10時点で調べ直した結果が下の節で、移行するかどうかはまだ決めていない。

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

OrbStack を残したまま併存させて試す。切り替えるかどうかは、下の検証の結果を見て決める。

socktainer の formula は `depends_on "container"` を持つので、brew で入れると pkg 版の container と重複する (socktainer/socktainer#392)。container を brew 管理へ寄せるかどうかを先に決める。

## タスク

- [ ] container の入手経路を決める (pkg のままか brew へ寄せるか)。brew へ寄せるなら Brewfile に載せる (ISSUE-95 の射程の議論と合わせる)
- [ ] container を1.5.0へ上げる。上げる前に、既存のイメージとボリュームが引き継がれるかを確かめる
- [ ] OrbStack と同時に動かしたときに、ポート・サブネット・DNS が衝突しないかを確かめる
- [ ] socktainer と素の `docker compose` で、実際に使う compose ファイルを起動できるか確かめる
- [ ] Container-Compose 1.2.0でも同じ compose ファイルを試し、socktainer と比べる
- [ ] 移行障害を実測する: inotify が届かないことの影響、多数のサービスを常駐させたときのメモリ、使っているイメージが arm64 で動くか
- [ ] 移行するかを決め、決めた結果を `home/.claude/references/host-environment.md` の隔離先コンテナの記述へ反映する
- [ ] 移行するなら、OrbStack.app と Docker.app、`/usr/local/bin/docker` の symlink、docker context の扱いを決める
- [ ] 自作した compose 互換ツールを畳むか続けるかを、そのリポジトリ側の Issue で決める

## 関連

- ISSUE-95 (Brewfile の射程が実機とずれている。OrbStack も container も Brewfile の外にある)
- apple/container#239、apple/container#2123 (compose を本体に入れない方針)
- apple/container#66 (Docker Engine API を提供しない)
- apple/container#141、apple/container#1809、apple/container#2142 (本体に欠けたままの機能)
- socktainer/socktainer#212 (compose 対応)、socktainer/socktainer#392 (formula の依存で container が重複する)
