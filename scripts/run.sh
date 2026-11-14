#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
task="${1:-test}"
case "$task" in test|demo|benchmark|all) ;; *) echo 'Usage: bash scripts/run.sh [test|demo|benchmark|all]' >&2; exit 2 ;; esac
mkdir -p build/classes
find src -name '*.java' -print > build/sources.txt
javac --release 17 -encoding UTF-8 -Xlint:all -Werror -d build/classes @build/sources.txt
if [[ "$task" == test || "$task" == all ]]; then
    java -cp build/classes edu.algorithms.matching.CorrectnessTests
fi
if [[ "$task" == demo || "$task" == all ]]; then
    java -cp build/classes edu.algorithms.matching.Demo
fi
if [[ "$task" == benchmark || "$task" == all ]]; then
    java -cp build/classes edu.algorithms.benchmark.BenchmarkRunner
fi
