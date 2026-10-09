# Build from any working directory and forward arguments to the Python builder.
$ErrorActionPreference = 'Stop'
$repositoryRoot = $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is required. Install it with: python -m pip install uv'
}
Push-Location -LiteralPath $repositoryRoot
try {
    & uv run --locked --group build --group dev python scripts/build_release.py @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
