# Aho-Corasick Algorithm - Java Bonus Task

A dependency-free Java 17+ implementation of multi-pattern exact matching, with a separate KMP baseline, independently checked test cases, and reproducible timing experiments.

**Student:** Sultanali Baltabay


**Measured results:** [analysis and tables](results/RESULTS.md) | [all 90 runs](results/benchmark-runs.csv) | [18 averages](results/benchmark-summary.csv)

## Run the project

Install a JDK, version 17 or newer; both `java` and `javac` must be on `PATH`. No Maven, Gradle, or third-party Java libraries are needed.

Windows PowerShell, from the repository directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 all
```

Linux/macOS or Git Bash:

```bash
bash scripts/run.sh all
```

Replace `all` with `test`, `demo`, or `benchmark` for a single operation. Each command compiles the code with `--release 17 -Xlint:all -Werror`. The benchmark overwrites the generated CSV files in `results/` with measurements from the current machine. After rerunning it, regenerate the reports using the optional Python command below to keep tables consistent.

Custom input after compiling:

```bash
java -cp build/classes edu.algorithms.matching.Demo ababa aba ba
```

The default demonstration searches `ahishers` for `he`, `she`, `his`, and `hers`. It returns `his` at `[1,4)`, `she` at `[3,6)`, `he` at `[4,6)`, and `hers` at `[4,8)`.

## Matching contract

- Searches are exact and case-sensitive. All occurrences, including overlaps, are reported.
- Every pattern keeps its original zero-based ID. Duplicate strings are distinct dictionary entries and produce distinct matches.
- Offsets are zero-based UTF-16 code-unit positions, following Java `String`; the end offset is exclusive. Non-ASCII text and emoji are supported, without normalization or case folding.
- An empty dictionary or text returns no matches. Null arguments are rejected. Empty patterns are rejected because matching at every boundary would require a separate explicit convention.
- `findAll(text)` returns immutable `Match` records. `forEachMatch(text, consumer)` emits occurrences without allocating a record per match. `countMatches(text)` uses that same enumeration callback for both algorithms.
- Match order is implementation-specific: Aho-Corasick emits by text position; KMP emits by pattern ID. Tests compare sorted match lists while preserving duplicate occurrences.
- Matchers copy the input dictionary and can be reused across independent searches. Adding patterns requires constructing a new matcher.

## How the algorithm works

1. **Trie:** insert every pattern, sharing common prefixes. A terminal state stores the IDs of patterns ending there.
2. **Failure links:** traverse the trie with a breadth-first queue. A state's failure target is the longest proper suffix of its prefix that is also a trie prefix. Root children fail to the root. For a child reached by symbol `c`, its failure target is the completed `c` transition from its parent's failure state.
3. **Output links:** each state points to its nearest terminal failure ancestor, or has no output link. Following this chain reports suffix patterns without copying their IDs into every descendant.
4. **Completed transitions:** missing edges are filled from the failure state's transitions during BFS. The search therefore makes one automaton transition per known text character. An unknown character resets the automaton to the root.
5. **Search:** scan left to right, emit direct terminal patterns and then follow output links. For a match ending at index `i`, its interval is `[i + 1 - pattern.length(), i + 1)`.

In the example, reaching `she` reports `she` directly and `he` through its output link. Failure links preserve useful suffix information after a mismatch instead of rescanning the text. The original algorithm describes matching multiple keywords in one pass [1].

## Time and space complexity

Let `k` be the number of patterns, `M` their total UTF-16 length, `S <= M + 1` the number of trie states, `sigma` the number of distinct UTF-16 symbols in the dictionary, `n` the text length, and `z` the number of reported occurrences, including duplicates.

| Operation | This Aho-Corasick implementation | Separate KMP for all patterns |
| --- | --- | --- |
| Preprocessing | Expected `O(M + S * sigma + k)` | `O(M + k)` |
| One search | Expected `O(n + z)` | `O(k * n + z)` |
| Total: build and one search | Expected `O(M + S * sigma + k + n + z)` | `O(M + k + k * n + z)` |
| Matcher auxiliary storage | `O(S * (sigma + 1) + k + sigma)` | `O(M + k)` |
| Streaming search auxiliary storage | `O(1)` | `O(1)` |
| Storing all matches | Additional `O(z)` | Additional `O(z)` |

The alphabet map uses expected constant-time hash lookups. The alphabet is compressed to symbols actually present in the dictionary, but **every state still has a dense transition array of size `sigma`**. This is why preprocessing and space explicitly include `S * sigma`. For a fixed-size alphabet, preprocessing becomes `O(M + k)` and storage is linear in `M + k`; it would be incorrect to omit `sigma` without that assumption. The `+1` in the storage bound accounts for states even when the alphabet is empty.

The matcher retains references to immutable input strings rather than copying their character content. If dictionary character storage is included, add `O(M)` to space. The BFS queue uses at most `O(S)` additional construction memory. Output lists contain only direct terminal IDs (`O(k)` total); output links avoid potentially large inherited-output copies. The input text itself occupies `O(n)` space outside the matcher.

KMP's prefix tables are built once per pattern. Each pattern then scans the text separately, causing `k` passes. KMP is attractive for a single or small number of patterns and has cheaper preprocessing; Aho-Corasick amortizes a larger automaton over many patterns and repeated searches. A large alphabet can make dense Aho-Corasick memory expensive, and output-heavy inputs force either algorithm to spend time reporting `z` occurrences.

## Correctness tests

Run `test` to execute:

- 14 named cases: the classic example, suffix outputs, nested overlaps, periodic overlaps, duplicates, empty text, empty dictionary, no matches, long patterns, unknown symbols, case and boundaries, Unicode/emoji, deep fallback, and embedded zero code units.
- Manually specified expected positions and overlap counts; invalid-input, defensive-copy, result-immutability, and repeated-search checks.
- 500 deterministic randomized cases checked against a separate naive substring implementation, not just against the other optimized algorithm.

The recorded local execution passed **3,108 assertions**. [Full verification log](results/verification.txt). GitHub Actions runs the same correctness suite on JDK 17 and 25. Exact match IDs and positions are also compared between Aho-Corasick and KMP for each of the nine benchmark inputs before timing.

## Experiment design and findings

All nine combinations of `k = 10, 100, 1000` and `n = 1000, 10000, 100000` are measured. Inputs use seeded lowercase random text and distinct patterns of length 3-12. Up to 20 patterns are inserted into separate text segments to guarantee positive matches; incidental matches are retained. Each case uses its own recorded seed and dictionary, so dictionary length, alphabet size, and match density can vary across cases. See [dataset metadata](results/datasets.csv).

There are 100 global warm-up rounds and 20 additional warm-up rounds per case, followed by **exactly five measured runs per algorithm per case**. Input generation, exact-result validation, and file output are excluded from timed intervals. Each measured run builds a new matcher and performs one search; `System.nanoTime()` [2] records build, search, and their sum. The arithmetic mean is calculated from five raw nanosecond measurements, before display rounding. Execution order alternates. Both searches enumerate every occurrence through the same counting callback, avoiding per-match list allocations during timing; materializing a result list has additional `O(z)` storage cost.

The result tables and measured discussion are generated from the committed CSV files in [RESULTS.md](results/RESULTS.md), and are included in the [report](docs/REPORT.md). They distinguish search speed from the cost of building an automaton for one text. Observed speedups are specific to this machine and workload. JVM compilation, scheduling, CPU power management, garbage collection, and five-sample variation still affect this experiment; warm-up does not eliminate them. Random lowercase inputs are not a worst-case or universal workload study. Space is analyzed theoretically and with transition-slot counts, not claimed as a measured Java heap footprint.

## Files and clean-code structure

```text
src/main/java/edu/algorithms/
  matching/                  # Aho-Corasick, KMP, shared contract, records, demo
  benchmark/                 # Seeded input generation and timing/CSV output
src/test/java/               # Independent correctness oracle and API tests
scripts/run.ps1, run.sh      # Dependency-free compile and run commands
scripts/build_report.py     # CSV validation and reproducible reports/chart
results/                    # Raw runs, averages, seeds, environment, verification
docs/REPORT.md              # Generated technical report
docs/HANDWRITTEN-CHECKLIST.md
output/pdf/                 # Printable technical report
.github/workflows/          # JDK 17 and 25 correctness checks
```

The matcher code has no console, filesystem, timing, or input-generation responsibilities. Classes have explicit roles, state is private, input dictionaries and results are immutable, and the two implementations share the matching contract and counting callback. The Java project uses only the standard library. Optional report generation uses Python and ReportLab:

```bash
python -m pip install reportlab pypdf
python scripts/build_report.py
```

The report builder validates that all 90 runs, 18 averages, five-run groups, match counts, and `build + search = total` values agree before generating output.

## Requirement checklist

| Requirement | Evidence |
| --- | --- |
| Java trie for multiple patterns | `AhoCorasick.buildTrie` |
| Failure links | `AhoCorasick.buildFailureAndOutputLinks` |
| Output links / suffix matches | `Node.output`, `emitMatches`, suffix-output tests |
| All occurrences | `findAll`, `forEachMatch`, overlap and duplicate tests |
| 10 / 100 / 1000 patterns | `BenchmarkRunner`, `results/datasets.csv` |
| 1000 / 10000 / 100000 characters | Full Cartesian product in `BenchmarkRunner` |
| `System.nanoTime()`, 5 runs and averages | Raw and summary CSV files, report tables |
| Time/space and trie/failure explanation | Complexity and algorithm sections above |
| Comparison with separate KMP | `KmpMultiPattern`, measured results, report discussion |
| Test cases, results, README, GitHub | This repository and its CI workflow |
| Approximately one handwritten page, in student's own words | **Separate student task**; see checklist below |

## References

1. A. V. Aho and M. J. Corasick, *Efficient String Matching: An Aid to Bibliographic Search*, Communications of the ACM 18(6), 333-340, 1975. [Original paper](https://cr.yp.to/bib/1975/aho.pdf), [DOI](https://doi.org/10.1145/360825.360855).
2. Oracle, Java SE 25, [`System.nanoTime()` documentation](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/System.html#nanoTime()). Elapsed time is calculated from the difference between two readings; nanosecond units do not guarantee nanosecond accuracy.
