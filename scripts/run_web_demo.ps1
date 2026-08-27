param(
    [string]$Address = "localhost",
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot
$env:PYTHONPATH = ".;scripts"

python -m streamlit run frontend_demo/app.py --server.address $Address --server.port $Port
