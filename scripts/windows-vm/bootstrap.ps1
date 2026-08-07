<#
.SYNOPSIS
    Windows 検証 VM に SSH 経路と開発ツールを用意する。冪等。

.DESCRIPTION
    winvm が前提とするゲスト側の状態を作る。何度実行しても結果は同じで、
    既にあるものには触れない。

    Windows PowerShell 5.1 で動く構文だけを使う。pwsh(7) 自身がこの
    スクリプトの導入対象なので、pwsh を前提にすると起動できない。

    SSH の構成 (capability / サービス / ファイアウォール) には管理者権限が
    要る。SSH セッションの管理者トークンは UAC でフィルタされることがあり、
    その場合は実行せず prlctl exec 経由を案内する。ツールの導入は非管理者でも
    通るため、権限が足りなくてもそこで止めない。

.PARAMETER AllowedSubnet
    sshd のファイアウォール規則で許可する送信元。既定は Parallels の共有
    ネットワーク。規則は Private プロファイル限定で作られるが、Parallels の
    共有ネットワークは Windows から Public と判定されるため広げる必要がある。
    ネットワーク全体を Private へ格下げすると探索や共有まで一括で緩むので、
    規則側だけを広げて送信元を絞る。

.PARAMETER PublicKey
    administrators_authorized_keys へ置く公開鍵 1 行。省略すると鍵の配置を
    飛ばす。既存の鍵は上書きしない。

.PARAMETER SkipSsh
    SSH の構成を飛ばす。ツールの導入だけしたいとき。

.PARAMETER SkipTools
    ツールの導入を飛ばす。SSH の構成だけしたいとき。

.EXAMPLE
    prlctl exec "<vm>" powershell -NoProfile -ExecutionPolicy Bypass -File C:\bootstrap.ps1

.EXAMPLE
    ssh <alias> "powershell -NoProfile -ExecutionPolicy Bypass -File C:\bootstrap.ps1 -SkipSsh"
#>
[CmdletBinding()]
param(
    [string] $AllowedSubnet = '10.211.55.0/24',
    [string] $PublicKey = '',
    [switch] $SkipSsh,
    [switch] $SkipTools,

    # dot-source して関数だけを取り込むためのスイッチ。Pester から使う。
    # scripts/ci/download-and-verify.sh の BASH_SOURCE guard と同じ役割を、
    # PowerShell には同等の仕組みが無いため明示的なフラグで果たす。
    [switch] $DotSourceOnly
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# 導入対象。Command はパスではなく「解決できる名前」で、これで導入を判定する。
# winget の台帳と実体は食い違い、MSIX 版 pwsh は Program Files に現れないので
# パスの存在で判定してはいけない。
$TOOLS = @(
    @{ Label = 'pwsh';  Id = 'Microsoft.PowerShell'; Command = 'pwsh' }
    @{ Label = 'git';   Id = 'Git.Git';              Command = 'git' }
    @{ Label = 'rustup'; Id = 'Rustlang.Rustup';     Command = 'rustup' }
    @{ Label = 'node';  Id = 'OpenJS.NodeJS';        Command = 'node' }
)

# 出力は winvm doctor に合わせる。判定だけでなく観測値を必ず並べ、
# 読めなかった項目は OK でも NG でもない第三の状態として出す。
function Write-Result {
    param(
        [Parameter(Mandatory = $true)][string] $State,
        [Parameter(Mandatory = $true)][string] $Label,
        [string] $Detail = ''
    )
    $tag = '[{0,-4}]' -f $State
    Write-Host ('{0} {1,-16}: {2}' -f $tag, $Label, $Detail)
}

# 検査機構そのものの故障を検出するための対照。
# 必ず解決できるはずの名前が解決できないなら、壊れているのは探索側である。
# 対照を混ぜないと「全件 MISSING」を「全部入っていない」と読んでしまう。
# 対照は引数にしてある。既定の cmd.exe は Windows でしか解決できないので、
# 固定するとこの関数自体を Windows 以外でテストできない。
function Assert-ProbeHealthy {
    param([string] $ControlCommand = 'cmd.exe')

    if (-not (Get-Command $ControlCommand -ErrorAction SilentlyContinue)) {
        throw ('コマンド探索が機能していない (対照の {0} すら解決できない)' -f $ControlCommand)
    }
}

function Test-Elevated {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal $identity
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-Tool {
    param([Parameter(Mandatory = $true)][string] $Command)
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

function Get-ToolSource {
    param([Parameter(Mandatory = $true)][string] $Command)
    $cmd = Get-Command $Command -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { return '' }
    if ($cmd.Source) { return $cmd.Source }
    return $cmd.Name
}

# PATH をレジストリの Machine / User スコープと併合する。
#
# 2 つの理由で要る。
#
# 1. winget が入れたツールの PATH は新しいプロセスにしか伝わらないので、
#    導入直後に同一セッションで検査するには読み直しが要る
# 2. セッションの PATH はレジストリより遅れることがある。rustup が
#    %USERPROFILE%\.cargo\bin を User PATH へ足した直後の SSH セッションでは
#    まだ載っておらず、導入済みなのに解決できず再導入が走った (実測)。
#    後から張り直したセッションには載っていたので、構造的な欠落ではなく反映の
#    遅れである。レジストリを直接読めばこの遅れに依存しない
#
# セッション固有の項目を落とさないよう、置き換えではなく併合する。
function Update-ProcessPath {
    $sources = @($env:Path)
    foreach ($scope in @('Machine', 'User')) {
        $sources += [Environment]::GetEnvironmentVariable('Path', $scope)
    }
    $env:Path = Merge-PathEntries -Sources $sources
}

# 複数の PATH 文字列を、順序を保ちつつ重複を除いて 1 本にまとめる。
#
# Update-ProcessPath から純粋な部分だけを切り出してある。レジストリの読み取りは
# .NET の静的メソッドで差し替えられないため、混ざったままだとこの併合規則を
# テストできない。
#
# 大小は区別しない。Windows のパスが case-insensitive なので、区別すると
# C:\Windows と c:\windows が別項目として両方残る。
function Merge-PathEntries {
    param([string[]] $Sources)

    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $merged = @()
    foreach ($source in $Sources) {
        if (-not $source) { continue }
        foreach ($entry in $source.Split(';')) {
            if (-not $entry) { continue }
            if ($seen.Add($entry)) { $merged += $entry }
        }
    }
    return ($merged -join ';')
}

function Install-Tool {
    param(
        [Parameter(Mandatory = $true)][hashtable] $Tool
    )

    if (Test-Tool $Tool.Command) {
        Write-Result 'SKIP' $Tool.Label ('導入済み ' + (Get-ToolSource $Tool.Command))
        return
    }

    if (-not (Test-Tool 'winget')) {
        Write-Result 'FAIL' $Tool.Label 'winget が無いので導入できない'
        return
    }

    # 非対話セッションでは同意を明示しないと winget が黙って止まる。
    winget install --id $Tool.Id --source winget --exact `
        --accept-package-agreements --accept-source-agreements `
        --silent --disable-interactivity | Out-Null
    $code = $LASTEXITCODE

    Update-ProcessPath

    if (Test-Tool $Tool.Command) {
        Write-Result 'NEW' $Tool.Label ('導入 ' + (Get-ToolSource $Tool.Command))
        return
    }

    # winget が成功を返しても解決できないことがある。台帳ではなく実体で判定し、
    # 判定できないことを成功と読み替えない。
    if ($code -eq 0) {
        Write-Result '??' $Tool.Label 'winget は成功したが同一セッションでは解決できない (新しいセッションで確認する)'
    }
    else {
        Write-Result 'FAIL' $Tool.Label ("winget が exit {0} で失敗" -f $code)
    }
}

function Initialize-RustToolchain {
    if (-not (Test-Tool 'rustup')) { return }

    # rustup があってもツールチェインが未導入なら rustc は解決できない。
    if (Test-Tool 'rustc') {
        Write-Result 'SKIP' 'rust toolchain' (& rustc --version)
        return
    }

    rustup default stable | Out-Null
    Update-ProcessPath

    if (Test-Tool 'rustc') {
        Write-Result 'NEW' 'rust toolchain' (& rustc --version)
    }
    else {
        Write-Result '??' 'rust toolchain' 'rustup default stable の後も rustc を解決できない'
    }
}

function Initialize-SshServer {
    param([Parameter(Mandatory = $true)][string] $Subnet)

    $capability = Get-WindowsCapability -Online -Name 'OpenSSH.Server*' |
        Select-Object -First 1
    if ($null -eq $capability) {
        Write-Result 'FAIL' 'OpenSSH capability' '候補が見つからない'
    }
    elseif ($capability.State -eq 'Installed') {
        Write-Result 'SKIP' 'OpenSSH capability' $capability.Name
    }
    else {
        Add-WindowsCapability -Online -Name $capability.Name | Out-Null
        Write-Result 'NEW' 'OpenSSH capability' $capability.Name
    }

    $service = Get-Service -Name 'sshd' -ErrorAction SilentlyContinue
    if ($null -eq $service) {
        Write-Result 'FAIL' 'sshd' 'サービスが存在しない'
    }
    else {
        if ((Get-Service -Name 'sshd').StartType -ne 'Automatic') {
            Set-Service -Name 'sshd' -StartupType Automatic
        }
        if ((Get-Service -Name 'sshd').Status -ne 'Running') {
            Start-Service -Name 'sshd'
        }
        $now = Get-Service -Name 'sshd'
        Write-Result 'OK' 'sshd' ('{0} / {1}' -f $now.Status, $now.StartType)
    }

    # 規則は OpenSSH の導入で作られるが Private プロファイル限定で入る。
    $rule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
    if ($null -eq $rule) {
        Write-Result 'FAIL' 'firewall' '規則 OpenSSH-Server-In-TCP が無い'
    }
    else {
        Set-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -Profile Any -RemoteAddress $Subnet
        $filter = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' |
            Get-NetFirewallAddressFilter
        Write-Result 'OK' 'firewall' ('Profile=Any RemoteAddress={0}' -f ($filter.RemoteAddress -join ','))
    }
}

function Initialize-AuthorizedKey {
    param([Parameter(Mandatory = $true)][string] $Key)

    $path = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'

    if (Test-Path $path) {
        $existing = Get-Content -Path $path -Raw
        if ($existing -and $existing.Contains($Key.Trim())) {
            Write-Result 'SKIP' 'authorized key' '同じ鍵が既にある'
            return
        }
        Write-Result 'FAIL' 'authorized key' '別の内容の鍵ファイルがある (上書きしない)'
        return
    }

    [IO.File]::WriteAllText($path, $Key.Trim() + [Environment]::NewLine)

    # 他に書ける主体があると sshd はファイルを黙って無視する。
    # グループ名は日本語 Windows でローカライズされうるので SID で指定する。
    # *S-1-5-32-544 = Administrators / *S-1-5-18 = SYSTEM
    icacls.exe $path /inheritance:r /grant '*S-1-5-32-544:F' /grant '*S-1-5-18:F' | Out-Null

    Write-Result 'NEW' 'authorized key' $path
}

# --- 本体 ---

function Invoke-Main {
    Assert-ProbeHealthy

    # 探索の前に必ず読み直す。セッションの PATH だけでは導入済みを見落とす。
    Update-ProcessPath

    Write-Host ''
    Write-Host ('ホスト   : {0}' -f $env:COMPUTERNAME)
    Write-Host ('ユーザー : {0}' -f ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME))
    Write-Host ('PowerShell : {0}' -f $PSVersionTable.PSVersion)
    Write-Host ''

    if ($script:SkipSsh) {
        Write-Result 'SKIP' 'SSH 構成' '-SkipSsh が指定された'
    }
    elseif (-not (Test-Elevated)) {
        # 権限不足を失敗として扱わない。この経路では実行できないという第三の状態。
        Write-Result '??' 'SSH 構成' '管理者権限が無いので実行しない (prlctl exec 経由で実行する)'
    }
    else {
        Initialize-SshServer -Subnet $script:AllowedSubnet
        if ($script:PublicKey) {
            Initialize-AuthorizedKey -Key $script:PublicKey
        }
        else {
            Write-Result 'SKIP' 'authorized key' '-PublicKey が未指定'
        }
    }

    Write-Host ''

    if ($script:SkipTools) {
        Write-Result 'SKIP' 'ツール導入' '-SkipTools が指定された'
    }
    else {
        foreach ($tool in $TOOLS) {
            Install-Tool -Tool $tool
        }
        Initialize-RustToolchain
    }

    Write-Host ''
    Write-Host '完了。winvm doctor で全体を確認する。'
}

if (-not $DotSourceOnly) {
    Invoke-Main
}
