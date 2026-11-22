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

# =============================================================================
# 持ち主の解決 (ghts_owner_from_args / ghts_owner_from_url) と設定の解釈
# =============================================================================

@test "owner_from_args: pr view 3 -R Acme/Web -> acme" {
    run ghts_owner_from_args pr view 3 -R Acme/Web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: --repo=acme/web -> acme" {
    run ghts_owner_from_args pr view 3 --repo=acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: --repo acme/web (separate value) -> acme" {
    run ghts_owner_from_args pr view 3 --repo Acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: -R HOST/OWNER/REPO -> acme" {
    run ghts_owner_from_args pr view 3 -R github.com/acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: -R URL -> acme" {
    run ghts_owner_from_args pr view 3 -R https://github.com/acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: -R wins over api endpoint" {
    run ghts_owner_from_args api repos/other/web -R acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: api repos/Acme/web/rulesets -> acme" {
    run ghts_owner_from_args api repos/Acme/web/rulesets
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: api /repos/acme/web -> acme" {
    run ghts_owner_from_args api /repos/acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: api orgs/acme/members -> acme" {
    run ghts_owner_from_args api orgs/acme/members
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: api users/bob -> bob" {
    run ghts_owner_from_args api users/bob
    [ "$status" -eq 0 ]
    [ "$output" = "bob" ]
}

@test "owner_from_args: api user -> empty" {
    run ghts_owner_from_args api user
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: api flags with values are not the endpoint" {
    run ghts_owner_from_args api -H "Accept: x" -X GET repos/acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: repo view acme/web -> acme" {
    run ghts_owner_from_args repo view acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: pr merge URL -> acme" {
    run ghts_owner_from_args pr merge https://github.com/acme/web/pull/3
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_args: pr list -> empty" {
    run ghts_owner_from_args pr list
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: search repos foo -> empty" {
    run ghts_owner_from_args search repos foo
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: pr create --base main --head feature/x -> empty" {
    run ghts_owner_from_args pr create --base main --head feature/x
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: pr checkout feature/x -> empty" {
    run ghts_owner_from_args pr checkout feature/x
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: pr merge 3 --body a/b -> empty" {
    run ghts_owner_from_args pr merge 3 --body a/b
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: release create v1 dist/x -> empty" {
    run ghts_owner_from_args release create v1 dist/x
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: workflow run .github/workflows/ci.yml -> empty" {
    run ghts_owner_from_args workflow run .github/workflows/ci.yml
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_args: issue create -t x/y -> empty" {
    run ghts_owner_from_args issue create -t x/y
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_url: scp style with .git" {
    run ghts_owner_from_url git@github.com:Acme/web.git
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_url: scp style without .git" {
    run ghts_owner_from_url git@github.com:acme/web
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_url: ssh scheme" {
    # リテラルの ssh://git@host/ は gitleaks の email-address に当たるので組み立てる
    local host=github.com
    run ghts_owner_from_url "ssh://git@${host}/acme/web"
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_url: https with .git" {
    run ghts_owner_from_url https://github.com/acme/web.git
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_url: https with trailing path" {
    run ghts_owner_from_url https://github.com/acme/web/pull/3
    [ "$status" -eq 0 ]
    [ "$output" = "acme" ]
}

@test "owner_from_url: other host (gitlab scp) -> empty" {
    run ghts_owner_from_url git@gitlab.com:acme/web.git
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "owner_from_url: GHES host -> empty" {
    run ghts_owner_from_url https://github.example.com/acme/web
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "valid_owner: acme-1 accepted" {
    run ghts_valid_owner acme-1
    [ "$status" -eq 0 ]
}

@test "valid_owner: rejects bad names" {
    local bad
    for bad in -acme acme/x 'a;b' ../x '' "$(printf 'a%.0s' $(seq 1 40))"; do
        run ghts_valid_owner "$bad"
        [ "$status" -ne 0 ] || { echo "accepted: $bad"; return 1; }
    done
}

@test "valid_owner: 39 chars accepted" {
    run ghts_valid_owner "$(printf 'a%.0s' $(seq 1 39))"
    [ "$status" -eq 0 ]
}

@test "valid_owner: trailing newline rejected" {
    run ghts_valid_owner "$(printf 'acme\nx')"
    [ "$status" -ne 0 ]
}

_write_config() {
    CONF="$BATS_TEST_TMPDIR/ghts.conf"
    printf '%s\n' "$@" >"$CONF"
}

@test "load_config: normal file sets three variables" {
    _write_config '# comment' '' 'vault=Dev Vault' 'default_owner=Acme' 'owner=Acme' '' 'owner=bob-2'
    ghts_load_config "$CONF"
    [ "$GHTS_VAULT" = "Dev Vault" ]
    [ "$GHTS_DEFAULT_OWNER" = "acme" ]
    [ "$GHTS_OWNERS" = "acme bob-2" ]
}

@test "load_config: missing vault -> rc 1" {
    _write_config 'default_owner=acme' 'owner=acme'
    run ghts_load_config "$CONF"
    [ "$status" -eq 1 ]
}

@test "load_config: missing default_owner -> rc 1" {
    _write_config 'vault=v' 'owner=acme'
    run ghts_load_config "$CONF"
    [ "$status" -eq 1 ]
}

@test "load_config: invalid owner line -> rc 1" {
    _write_config 'vault=v' 'default_owner=acme' 'owner=a;b'
    run ghts_load_config "$CONF"
    [ "$status" -eq 1 ]
}

@test "load_config: missing file -> rc 1" {
    run ghts_load_config "$BATS_TEST_TMPDIR/nonexistent.conf"
    [ "$status" -eq 1 ]
}

@test "load_config: last line without newline is read" {
    CONF="$BATS_TEST_TMPDIR/ghts.conf"
    printf 'vault=v\ndefault_owner=acme\nowner=zed' >"$CONF"
    ghts_load_config "$CONF"
    [ "$GHTS_OWNERS" = "zed" ]
}

@test "load_config: file is never sourced" {
    local work="$BATS_TEST_TMPDIR/work"
    mkdir -p "$work"
    CONF="$work/ghts.conf"
    printf '%s\n' 'vault=$(touch pwned)' 'default_owner=acme' >"$CONF"
    cd "$work"
    ghts_load_config "$CONF"
    # 設定を実際に読んだ陽性対照: 値がリテラルのまま入る
    [ "$GHTS_VAULT" = '$(touch pwned)' ]
    [ ! -e "$work/pwned" ]
}

@test "has_owner: member and non-member" {
    GHTS_OWNERS="acme bob-2"
    ghts_has_owner acme
    ghts_has_owner bob-2
    run ghts_has_owner ac
    [ "$status" -ne 0 ]
    run ghts_has_owner ""
    [ "$status" -ne 0 ]
}
