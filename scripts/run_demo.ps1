param(
    [string]$Query = "公司违法解除劳动合同怎么办？"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot
$env:PYTHONPATH = ".;scripts"

Write-Host "Running test suite..."
python -m pytest tests

Write-Host "Running deterministic RAG demo..."
python scripts/ask_legal.py $Query --provider mock
