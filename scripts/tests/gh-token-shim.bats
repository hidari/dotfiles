#!/usr/bin/env bats
# =============================================================================
# gh-token-shim の操作分類 (ghts_classify) のテスト
# =============================================================================

load test_helper

LIB="$REPO_ROOT/scripts/gh-token-shim/lib.sh"

setup() {
    # shellcheck source=/dev/null
    source "$LIB"
}

@test "classify: --version -> none" {
    run ghts_classify --version
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: version -> none" {
    run ghts_classify version
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: help -> none" {
    run ghts_classify help
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: help pr -> none" {
    run ghts_classify help pr
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: completion -s zsh -> none" {
    run ghts_classify completion -s zsh
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: auth status -> none" {
    run ghts_classify auth status
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: auth logout -> none" {
    run ghts_classify auth logout
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: (no args) -> none" {
    run ghts_classify
    [ "$status" -eq 0 ]
    [ "$output" = "none" ]
}

@test "classify: pr list -> read" {
    run ghts_classify pr list
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: pr view 3 -> read" {
    run ghts_classify pr view 3
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: pr create --fill -> read" {
    run ghts_classify pr create --fill
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: pr comment 3 --body-file x -> read" {
    run ghts_classify pr comment 3 --body-file x
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: issue create -> read" {
    run ghts_classify issue create
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: run view 1 -> read" {
    run ghts_classify run view 1
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: run watch 1 -> read" {
    run ghts_classify run watch 1
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: co 3 -> read" {
    run ghts_classify co 3
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: api repos/a/b -> read" {
    run ghts_classify api repos/a/b
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: api -X GET repos/a/b -> read" {
    run ghts_classify api -X GET repos/a/b
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: api --method=HEAD repos/a/b -> read" {
    run ghts_classify api --method=HEAD repos/a/b
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: api graphql -f query='query { viewer { login } }' -> read" {
    run ghts_classify api graphql -f query='query { viewer { login } }'
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: release view v1 -> read" {
    run ghts_classify release view v1
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: release list -> read" {
    run ghts_classify release list
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: repo view a/b -> read" {
    run ghts_classify repo view a/b
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: repo clone a/b -> read" {
    run ghts_classify repo clone a/b
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: ruleset list -> read" {
    run ghts_classify ruleset list
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: secret list -> read" {
    run ghts_classify secret list
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: pr merge 3 --squash -> write" {
    run ghts_classify pr merge 3 --squash
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: release create v1 -> write" {
    run ghts_classify release create v1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: release upload v1 f -> write" {
    run ghts_classify release upload v1 f
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: release delete-asset v1 f -> write" {
    run ghts_classify release delete-asset v1 f
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: repo sync -> write" {
    run ghts_classify repo sync
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: workflow run ci.yml -> write" {
    run ghts_classify workflow run ci.yml
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: run rerun 1 -> write" {
    run ghts_classify run rerun 1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: run cancel 1 -> write" {
    run ghts_classify run cancel 1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: secret set X -> write" {
    run ghts_classify secret set X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: variable delete X -> write" {
    run ghts_classify variable delete X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: cache delete 1 -> write" {
    run ghts_classify cache delete 1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api -X POST repos/a/b/x -> write" {
    run ghts_classify api -X POST repos/a/b/x
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api -XPOST repos/a/b/x -> write" {
    run ghts_classify api -XPOST repos/a/b/x
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api --method=patch repos/a/b -> write" {
    run ghts_classify api --method=patch repos/a/b
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api repos/a/b/labels -f name=x -> write" {
    run ghts_classify api repos/a/b/labels -f name=x
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api repos/a/b -Fx=1 -> write" {
    run ghts_classify api repos/a/b -Fx=1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api repos/a/b --input body.json -> write" {
    run ghts_classify api repos/a/b --input body.json
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api graphql -f query='mutation { x }' -> write" {
    run ghts_classify api graphql -f query='mutation { x }'
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api graphql --input q.json -> write" {
    run ghts_classify api graphql --input q.json
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: api graphql -F query=@q.graphql -> write" {
    run ghts_classify api graphql -F query=@q.graphql
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: repo create a/b --private -> admin" {
    run ghts_classify repo create a/b --private
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo delete a/b --yes -> admin" {
    run ghts_classify repo delete a/b --yes
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo edit --visibility public -> admin" {
    run ghts_classify repo edit --visibility public
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo rename x -> admin" {
    run ghts_classify repo rename x
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo archive -> admin" {
    run ghts_classify repo archive
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo unarchive -> admin" {
    run ghts_classify repo unarchive
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo fork a/b -> admin" {
    run ghts_classify repo fork a/b
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo deploy-key add k -> admin" {
    run ghts_classify repo deploy-key add k
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo autolink create p u -> admin" {
    run ghts_classify repo autolink create p u
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo deploy-key list -> read" {
    run ghts_classify repo deploy-key list
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: repo autolink view 1 -> read" {
    run ghts_classify repo autolink view 1
    [ "$status" -eq 0 ]
    [ "$output" = "read" ]
}

@test "classify: repo deploy-key delete 1 -> admin" {
    run ghts_classify repo deploy-key delete 1
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: repo autolink delete 1 -> admin" {
    run ghts_classify repo autolink delete 1
    [ "$status" -eq 0 ]
    [ "$output" = "admin" ]
}

@test "classify: release delete v1 -> write" {
    run ghts_classify release delete v1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: release edit v1 -> write" {
    run ghts_classify release edit v1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: workflow enable x -> write" {
    run ghts_classify workflow enable x
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: workflow disable x -> write" {
    run ghts_classify workflow disable x
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: run delete 1 -> write" {
    run ghts_classify run delete 1
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: secret delete X -> write" {
    run ghts_classify secret delete X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: secret remove X -> write" {
    run ghts_classify secret remove X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: variable set X -> write" {
    run ghts_classify variable set X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}

@test "classify: variable remove X -> write" {
    run ghts_classify variable remove X
    [ "$status" -eq 0 ]
    [ "$output" = "write" ]
}
