#!/usr/bin/env bats
# run-bats.bats が子プロセスとして渡す fixture。
# uncovered タグ付きのテストしか持たない。本体は走れば必ず赤くなる。

# bats test_tags=uncovered
@test "uncovered only: the body does not run in CI" {
    false
}
