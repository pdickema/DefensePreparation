param(
    [Parameter(Position = 0)]
    [string]$Command = "help",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$PythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "Could not find .venv\Scripts\python.exe."
    Write-Host "Create the virtual environment first:"
    Write-Host '  py -3.11 -m venv .venv'
    Write-Host '  .\.venv\Scripts\python.exe -m pip install -e ".[dev]"'
    exit 1
}

$Aliases = @{
    "all" = "run-all"
    "run" = "run-all"
    "preflight" = "preflight-pdfs"
    "scan" = "scan-pdfs"
    "manifest" = "validate-manifest"
    "export" = "export-llm"
    "llm" = "export-llm"
}

$PipelineCommand = $Command.ToLowerInvariant()
if ($Aliases.ContainsKey($PipelineCommand)) {
    $PipelineCommand = $Aliases[$PipelineCommand]
}

if ($PipelineCommand -eq "help") {
    Write-Host "Defense paper pipeline launcher"
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\pipeline.ps1 all"
    Write-Host "  .\pipeline.ps1 preflight"
    Write-Host "  .\pipeline.ps1 scan"
    Write-Host "  .\pipeline.ps1 manifest"
    Write-Host "  .\pipeline.ps1 process"
    Write-Host "  .\pipeline.ps1 chunk"
    Write-Host "  .\pipeline.ps1 report"
    Write-Host "  .\pipeline.ps1 defense-prep"
    Write-Host "  .\pipeline.ps1 export"
    Write-Host '  .\pipeline.ps1 query "your question"'
    Write-Host ""
    & $PythonExe -m paper_pipeline.cli --help
    exit $LASTEXITCODE
}

& $PythonExe -m paper_pipeline.cli $PipelineCommand @RemainingArgs
exit $LASTEXITCODE
