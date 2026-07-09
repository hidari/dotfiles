#!/usr/bin/env bats
# =============================================================================
# bootstrap.sh: Claude plugin セットアップのテスト
# =============================================================================

load test_helper

setup() {
    setup_test_home
    load_bootstrap_functions

    DRY_RUN=false
    FORCE_MODE=false
}

teardown() {
    teardown_test_home
}

# テスト用の標準 settings.json を書き出す
# - enabledPlugins: true/false 混在
# - extraKnownMarketplaces: github / git / directory / settings(inline) の 4 種
make_settings() {
    cat > "$TEST_HOME/settings.json" <<'JSON'
{
  "enabledPlugins": {
    "code-review@claude-plugins-official": true,
    "modern-web-guidance@googlechrome": true,
    "disabled-one@somewhere": false
  },
  "extraKnownMarketplaces": {
    "superpowers-marketplace": { "source": { "source": "github", "repo": "obra/superpowers-marketplace" } },
    "googlechrome": { "source": { "source": "git", "url": "https://github.com/GoogleChrome/modern-web-guidance.git" } },
    "hidari-plugins": { "source": { "source": "directory", "path": "/some/dir" } },
    "inline-one": { "source": { "source": "settings" } }
  }
}
JSON
}

# =============================================================================
# claude_plugin_targets: 純粋パース関数
# =============================================================================

@test "claude_plugin_targets: emits github/git/directory marketplaces as name<TAB>source" {
    make_settings

    run claude_plugin_targets "$TEST_HOME/settings.json"

    [ "$status" -eq 0 ]
    echo "$output" | grep -qF $'marketplace\tsuperpowers-marketplace\tobra/superpowers-marketplace'
    echo "$output" | grep -qF $'marketplace\tgooglechrome\thttps://github.com/GoogleChrome/modern-web-guidance.git'
    echo "$output" | grep -qF $'marketplace\thidari-plugins\t/some/dir'
}

@test "claude_plugin_targets: skips inline (settings) source marketplaces" {
    make_settings

    run claude_plugin_targets "$TEST_HOME/settings.json"

    [ "$status" -eq 0 ]
    ! echo "$output" | grep -q "inline-one"
}

@test "claude_plugin_targets: emits only enabled (true) plugins" {
    make_settings

    run claude_plugin_targets "$TEST_HOME/settings.json"

    [ "$status" -eq 0 ]
    echo "$output" | grep -qF $'plugin\tcode-review@claude-plugins-official'
    echo "$output" | grep -qF $'plugin\tmodern-web-guidance@googlechrome'
    # false の plugin は除外される
    ! echo "$output" | grep -q "disabled-one"
}

@test "claude_plugin_targets: empty settings.json produces no output and does not fail" {
    echo '{}' > "$TEST_HOME/settings.json"

    run claude_plugin_targets "$TEST_HOME/settings.json"

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

# =============================================================================
# setup_claude_plugins: オーケストレーション（fake claude を使用）
# =============================================================================

@test "setup_claude_plugins: dry-run prints planned commands without invoking claude" {
    make_settings
    setup_fake_claude
    DRY_RUN=true

    run setup_claude_plugins "$TEST_HOME/settings.json"

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] claude plugin marketplace add obra/superpowers-marketplace"
    assert_contains "$output" "[DRY-RUN] claude plugin install code-review@claude-plugins-official"
    # dry-run では実際の claude を一切呼ばない（ログが空）
    [ ! -s "$FAKE_CLAUDE_LOG" ]
}

@test "setup_claude_plugins: skips gracefully when claude is not installed" {
    make_settings
    mkdir -p "$TEST_HOME/empty"

    # claude を含まない PATH で実行し、終了後に必ず PATH を復元してから検証する
    local saved_path="$PATH"
    export PATH="$TEST_HOME/empty"
    run setup_claude_plugins "$TEST_HOME/settings.json"
    export PATH="$saved_path"

    [ "$status" -eq 0 ]
    # スキップ理由を示す正確なメッセージを検証する（部分一致の弱い assertion を避ける）
    assert_contains "$output" "claude not found; skipping Claude plugin setup"
}

@test "setup_claude_plugins: registers new marketplaces and installs new plugins" {
    make_settings
    setup_fake_claude
    export FAKE_MARKETPLACES_JSON='[]'
    export FAKE_PLUGINS_JSON='[]'

    run setup_claude_plugins "$TEST_HOME/settings.json"

    [ "$status" -eq 0 ]
    grep -qF 'marketplace add obra/superpowers-marketplace' "$FAKE_CLAUDE_LOG"
    grep -qF 'marketplace add https://github.com/GoogleChrome/modern-web-guidance.git' "$FAKE_CLAUDE_LOG"
    grep -qF 'marketplace add /some/dir' "$FAKE_CLAUDE_LOG"
    # code-review@claude-plugins-official は extraKnownMarketplaces に無い（組み込み marketplace 想定）が
    # plugin install は試行される
    grep -qF 'install code-review@claude-plugins-official' "$FAKE_CLAUDE_LOG"
    grep -qF 'install modern-web-guidance@googlechrome' "$FAKE_CLAUDE_LOG"
}

@test "setup_claude_plugins: skips already-registered marketplaces and installed plugins" {
    make_settings
    setup_fake_claude
    export FAKE_MARKETPLACES_JSON='[{"name":"googlechrome"}]'
    export FAKE_PLUGINS_JSON='[{"id":"modern-web-guidance@googlechrome"}]'

    run setup_claude_plugins "$TEST_HOME/settings.json"

    [ "$status" -eq 0 ]
    # 既存のものは add / install しない
    ! grep -qF 'marketplace add https://github.com/GoogleChrome/modern-web-guidance.git' "$FAKE_CLAUDE_LOG"
    ! grep -qF 'install modern-web-guidance@googlechrome' "$FAKE_CLAUDE_LOG"
    # 未登録 / 未インストールのものは実行する
    grep -qF 'marketplace add obra/superpowers-marketplace' "$FAKE_CLAUDE_LOG"
    grep -qF 'install code-review@claude-plugins-official' "$FAKE_CLAUDE_LOG"
    # スキップしたことがログに出る
    assert_contains "$output" "already"
}

@test "setup_claude_plugins: continues best-effort when one install fails" {
    make_settings
    setup_fake_claude
    export FAKE_MARKETPLACES_JSON='[]'
    export FAKE_PLUGINS_JSON='[]'
    export FAKE_INSTALL_FAIL='code-review@claude-plugins-official'

    run setup_claude_plugins "$TEST_HOME/settings.json"

    # 1 つ失敗しても全体は止めず（status 0）後続の install も試みる
    [ "$status" -eq 0 ]
    grep -qF 'install code-review@claude-plugins-official' "$FAKE_CLAUDE_LOG"
    grep -qF 'install modern-web-guidance@googlechrome' "$FAKE_CLAUDE_LOG"
    # 失敗した install の「後に」後続の install が試行される（= best-effort で継続している証跡）
    local log_content
    log_content="$(cat "$FAKE_CLAUDE_LOG")"
    assert_contains_in_order "$log_content" "install code-review@claude-plugins-official" "install modern-web-guidance@googlechrome"
    # 失敗は正確なメッセージで警告される
    assert_contains "$output" "Failed to install plugin (skipped):"
}
