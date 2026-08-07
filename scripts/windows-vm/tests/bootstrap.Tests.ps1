<#
scripts/windows-vm/bootstrap.ps1 の単体テスト (Pester)

このスクリプトが実際に仕事をするのは Windows ゲスト上だけなので、Windows 専用
コマンドレットを叩く関数 (Initialize-SshServer など) はここでは検証しない。
それらは実機の live smoke が担う。

ここで pin するのは、環境に依存せず決まるはずの規則である。

- ファイルの符号化 (BOM の有無)。Windows PowerShell 5.1 は BOM の無い .ps1 を
  ANSI コードページとして読むため、欠けると ja-JP 環境でだけ構文エラーになる
- PATH の併合規則 (順序保持・大小を区別しない重複除去・空要素の除去)
- 導入判定がパスの存在ではなく名前の解決可否で行われること
- dot-source ガードが効いていること (取り付けの検査)

モックは使わない。macOS と Linux には winget も Windows 専用コマンドも無いので、
その不在がそのまま負の対照になる。
#>

BeforeAll {
    $script:ScriptDir = Split-Path -Parent $PSScriptRoot
    $script:ScriptPath = Join-Path $script:ScriptDir 'bootstrap.ps1'

    # 本体を走らせずに関数だけを取り込む
    . $script:ScriptPath -DotSourceOnly
}

Describe 'ファイルの符号化' {
    It 'UTF-8 BOM で始まる' {
        $bytes = [System.IO.File]::ReadAllBytes($script:ScriptPath)
        $bytes.Length | Should -BeGreaterThan 3
        $bytes[0] | Should -Be 0xEF
        $bytes[1] | Should -Be 0xBB
        $bytes[2] | Should -Be 0xBF
    }
}

Describe '可搬性' {
    It '特定ユーザーの Windows ホームを埋め込まない' {
        # gitleaks の custom ルールは /Users/<name> を見るが Windows 形式は見ない。
        # 例示のパスに開発機のユーザー名が混ざると、配布先で解決せず気づけない。
        $text = Get-Content -Path $script:ScriptPath -Raw
        $text | Should -Not -Match 'C:\\Users\\[A-Za-z]'
    }
}

Describe 'dot-source ガード' {
    It '-DotSourceOnly を付けると本体が走らない' {
        # 取り付けの検査。ガードが外れると、この呼び出しで導入処理が動いてしまう。
        $output = & (Get-Process -Id $PID).Path -NoProfile -Command @"
. '$($script:ScriptPath)' -DotSourceOnly
Write-Output 'LOADED_ONLY'
"@
        $joined = ($output | Out-String)
        $joined | Should -Match 'LOADED_ONLY'
        $joined | Should -Not -Match 'winvm doctor'
    }

    It '-DotSourceOnly を外すと本体が走る' {
        # 上の検査の対照。本体がそもそも何も出さないなら、ガードが外れていても
        # 上の検査は通ってしまう。
        #
        # 何が出るかは環境で変わる (Windows ならヘッダ、それ以外は対照コマンドの
        # 不在で throw) ので、内容ではなく「空でないこと」を見る。
        $output = & (Get-Process -Id $PID).Path -NoProfile -Command @"
`$ErrorActionPreference = 'Continue'
. '$($script:ScriptPath)' -SkipSsh -SkipTools
"@ 2>&1
        ($output | Out-String).Trim() | Should -Not -Be ''
    }
}

Describe 'Merge-PathEntries' {
    It '単一の source をそのまま返す' {
        Merge-PathEntries -Sources @('C:\a;C:\b') | Should -Be 'C:\a;C:\b'
    }

    It '複数の source を順に連結する' {
        Merge-PathEntries -Sources @('C:\a', 'C:\b') | Should -Be 'C:\a;C:\b'
    }

    It '重複を除いて最初の出現順を保つ' {
        Merge-PathEntries -Sources @('C:\a;C:\b', 'C:\b;C:\c') | Should -Be 'C:\a;C:\b;C:\c'
    }

    It '大小を区別せず重複とみなす' {
        # 区別すると C:\Windows と c:\windows が両方残る
        Merge-PathEntries -Sources @('C:\Windows', 'c:\windows') | Should -Be 'C:\Windows'
    }

    It '空の要素を落とす' {
        Merge-PathEntries -Sources @('C:\a;;C:\b') | Should -Be 'C:\a;C:\b'
    }

    It '空文字の source を無視する' {
        Merge-PathEntries -Sources @('C:\a', '', 'C:\b') | Should -Be 'C:\a;C:\b'
    }

    It 'すべて空なら空文字を返す' {
        Merge-PathEntries -Sources @('', '') | Should -Be ''
    }
}

Describe 'Test-Tool' {
    It '解決できる名前に真を返す' {
        Test-Tool 'Get-Item' | Should -BeTrue
    }

    It '解決できない名前に偽を返す' {
        Test-Tool 'definitely-not-a-real-command-x9f2' | Should -BeFalse
    }
}

Describe 'Get-ToolSource' {
    It '解決できない名前に空文字を返す' {
        Get-ToolSource 'definitely-not-a-real-command-x9f2' | Should -Be ''
    }

    It '解決できる名前に空でない値を返す' {
        Get-ToolSource 'Get-Item' | Should -Not -Be ''
    }
}

Describe 'Assert-ProbeHealthy' {
    It '対照が解決できるとき throw しない' {
        { Assert-ProbeHealthy -ControlCommand 'Get-Item' } | Should -Not -Throw
    }

    It '対照が解決できないとき throw する' {
        # 探索機構が壊れている状態。ここで止めないと「全件 MISSING」を
        # 「全部入っていない」と読んでしまう。
        { Assert-ProbeHealthy -ControlCommand 'definitely-not-a-real-command-x9f2' } |
            Should -Throw -ExpectedMessage '*コマンド探索が機能していない*'
    }

    It '既定の対照は cmd.exe である' {
        # Windows で意味を持つ対照であることを pin する。既定が別の名前へ
        # すり替わると、Windows 上で常に真になる無意味な検査になりうる。
        $default = (Get-Command Assert-ProbeHealthy).Parameters['ControlCommand']
        $ast = (Get-Command Assert-ProbeHealthy).ScriptBlock.Ast
        $default | Should -Not -BeNullOrEmpty
        $ast.Extent.Text | Should -Match "ControlCommand = 'cmd\.exe'"
    }
}

Describe 'Install-Tool' {
    It '解決できるツールは winget を呼ばず SKIP を出す' {
        $tool = @{ Label = 'probe'; Id = 'Irrelevant.Id'; Command = 'Get-Item' }
        $output = Install-Tool -Tool $tool 6>&1 | Out-String
        $output | Should -Match 'SKIP'
        $output | Should -Match 'probe'
    }

    It '解決できず winget も無い環境では FAIL を出す' {
        # macOS と Linux には winget が無いので、この分岐は自然に踏める
        if (Test-Tool 'winget') {
            Set-ItResult -Skipped -Because 'winget がある環境ではこの分岐に入らない'
            return
        }
        $tool = @{ Label = 'absent'; Id = 'Irrelevant.Id'; Command = 'definitely-not-a-real-command-x9f2' }
        $output = Install-Tool -Tool $tool 6>&1 | Out-String
        $output | Should -Match 'FAIL'
        $output | Should -Match 'winget'
    }
}

Describe 'Write-Result' {
    It '状態とラベルと観測値を 1 行に並べる' {
        $output = Write-Result 'OK' 'label' 'detail' 6>&1 | Out-String
        $output | Should -Match '\[OK'
        $output | Should -Match 'label'
        $output | Should -Match 'detail'
    }

    It '観測値が空でも状態とラベルは出す' {
        $output = Write-Result 'SKIP' 'label' 6>&1 | Out-String
        $output | Should -Match '\[SKIP'
        $output | Should -Match 'label'
    }
}

Describe 'TOOLS' {
    It '各要素が Label と Id と Command を持つ' {
        $TOOLS.Count | Should -BeGreaterThan 0
        foreach ($tool in $TOOLS) {
            $tool.Label | Should -Not -BeNullOrEmpty
            $tool.Id | Should -Not -BeNullOrEmpty
            $tool.Command | Should -Not -BeNullOrEmpty
        }
    }

    It 'Id が重複しない' {
        $ids = $TOOLS | ForEach-Object { $_.Id }
        ($ids | Select-Object -Unique).Count | Should -Be $ids.Count
    }

    It 'winvm が要求するものを含む' {
        # winvm run は VM 側の git を使い、winvm health は pwsh(7) を要求する。
        $commands = @($TOOLS | ForEach-Object { $_.Command })
        $commands | Should -Contain 'pwsh'
        $commands | Should -Contain 'git'
    }

    It 'ビルド用ツールチェインを含まない' {
        # 基盤の線は winvm の要求で決まる。ここに Rust や Node を足すと、
        # 分割できない単位を分割して配ることになる。Windows の Rust は MSVC の
        # link.exe が無いと何もビルドできず、rustup だけでは「導入済みだが
        # 使えない」状態になる。ツールチェインは必要とするプロジェクトが持つ。
        $commands = @($TOOLS | ForEach-Object { $_.Command })
        foreach ($excluded in 'rustup', 'rustc', 'cargo', 'node', 'npm', 'pnpm') {
            $commands | Should -Not -Contain $excluded
        }
    }
}
