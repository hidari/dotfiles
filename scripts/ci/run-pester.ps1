<#
.SYNOPSIS
    Pester テストを走らせ、件数まで検査して結果を返す。

.DESCRIPTION
    Invoke-Pester を直接呼ばずこのラッパを通すのは、Pester が「テストが 1 件も
    見つからなかった」場合にも成功として終わるためである。テストファイルを消したり
    パスを打ち間違えたりしても緑になり、検査が消えたことに気づけない。

    ここでは失敗件数だけでなく総件数も見る。0 件は健全ではなく「そもそも見ていない」
    状態として落とす。

.PARAMETER Path
    テストを探す起点。

.PARAMETER MinimumCount
    最低限見つかるべきテスト件数。実際の件数がこれを下回ったら落とす。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $Path,
    [int] $MinimumCount = 1
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Module -ListAvailable -Name Pester)) {
    Write-Error 'Pester が見つからない。Install-Module Pester で導入する'
    exit 1
}

try {
    $result = Invoke-Pester -Path $Path -Output Detailed -PassThru
}
catch {
    # テストファイルが 1 件も無いとき Pester 自身がここへ落とす。
    # 件数ガードが守るのはこの先、「ファイルはあるがテストが 0 件」の方である。
    Write-Error ('Pester を起動できない: {0}' -f $_.Exception.Message)
    exit 1
}

if ($null -eq $result) {
    Write-Error 'Pester が結果を返さなかった'
    exit 1
}

Write-Host ''
Write-Host ('実行 {0} 件 / 失敗 {1} 件 / skip {2} 件' -f $result.TotalCount, $result.FailedCount, $result.SkippedCount)

if ($result.TotalCount -lt $MinimumCount) {
    Write-Error ('テストが {0} 件しか見つからない (最低 {1} 件を期待)。検査が消えている' -f $result.TotalCount, $MinimumCount)
    exit 1
}

if ($result.FailedCount -gt 0) {
    exit 1
}

exit 0
