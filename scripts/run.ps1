param(
    [ValidateSet('test', 'demo', 'benchmark', 'all')]
    [string]$Task = 'test'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    New-Item -ItemType Directory -Path 'build/classes' -Force | Out-Null
    $sourceFiles = @(Get-ChildItem -LiteralPath 'src' -Recurse -Filter '*.java' | ForEach-Object FullName)
    & javac --release 17 -encoding UTF-8 -Xlint:all -Werror -d build/classes @sourceFiles
    if ($LASTEXITCODE -ne 0) { throw 'Java compilation failed.' }
    if ($Task -in @('test', 'all')) {
        & java -cp build/classes edu.algorithms.matching.CorrectnessTests
        if ($LASTEXITCODE -ne 0) { throw 'Correctness tests failed.' }
    }
    if ($Task -in @('demo', 'all')) {
        & java -cp build/classes edu.algorithms.matching.Demo
        if ($LASTEXITCODE -ne 0) { throw 'Demo failed.' }
    }
    if ($Task -in @('benchmark', 'all')) {
        & java -cp build/classes edu.algorithms.benchmark.BenchmarkRunner
        if ($LASTEXITCODE -ne 0) { throw 'Benchmark failed.' }
    }
} finally {
    Pop-Location
}
