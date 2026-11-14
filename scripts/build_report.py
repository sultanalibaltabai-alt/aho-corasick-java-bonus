"""Validate the Java experiment and generate Markdown, vector chart, and PDF reports.

Optional dependencies: reportlab, pypdf. Java compilation/benchmarking does not need Python.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from xml.sax.saxutils import escape

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
DOCS = ROOT / "docs"
PDF = ROOT / "output" / "pdf" / "Aho-Corasick-Report.pdf"
BLUE = colors.HexColor("#173B57")
TEAL = colors.HexColor("#00877F")
ORANGE = colors.HexColor("#D57728")
GRAY = colors.HexColor("#566775")
PALE = colors.HexColor("#EEF4F7")
COUNTS = (10, 100, 1000)
LENGTHS = (1000, 10000, 100000)
ALGORITHMS = ("Aho-Corasick", "KMP")


def read_csv(name):
    with (RESULTS / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def load_and_validate():
    raw = read_csv("benchmark-runs.csv")
    summaries = read_csv("benchmark-summary.csv")
    datasets = read_csv("datasets.csv")
    if (len(raw), len(summaries), len(datasets)) != (90, 18, 9):
        raise ValueError("Expected 90 raw runs, 18 summary rows, and 9 datasets.")
    groups = defaultdict(list)
    for row in raw:
        key = (row["algorithm"], int(row["patterns"]), int(row["text_length"]))
        groups[key].append(row)
        if int(row["build_ns"]) + int(row["search_ns"]) != int(row["total_ns"]):
            raise ValueError("Build and search durations do not sum to total.")
        if min(int(row[field]) for field in ("build_ns", "search_ns", "total_ns")) <= 0:
            raise ValueError("Timing must be positive.")
    expected = {(algorithm, k, n) for algorithm in ALGORITHMS for k in COUNTS for n in LENGTHS}
    if set(groups) != expected:
        raise ValueError("The experiment does not cover the full required matrix.")
    indexed = {}
    for row in summaries:
        key = (row["algorithm"], int(row["patterns"]), int(row["text_length"]))
        if key in indexed:
            raise ValueError("Duplicate summary row.")
        indexed[key] = row
        group = groups[key]
        if sorted(int(item["run"]) for item in group) != [1, 2, 3, 4, 5] or int(row["runs"]) != 5:
            raise ValueError("Every algorithm/case must have exactly five distinct runs.")
        for field in ("build_ns", "search_ns", "total_ns"):
            actual_mean = mean(int(item[field]) for item in group)
            if not math.isclose(actual_mean, float(row["avg_" + field]), abs_tol=0.051, rel_tol=0):
                raise ValueError("Incorrect reported arithmetic mean.")
        if int(row["min_search_ns"]) != min(int(item["search_ns"]) for item in group):
            raise ValueError("Incorrect search minimum.")
        if int(row["max_search_ns"]) != max(int(item["search_ns"]) for item in group):
            raise ValueError("Incorrect search maximum.")
        if {int(item["matches"]) for item in group} != {int(row["matches"])}:
            raise ValueError("Match counts differ within one group.")
    if set(indexed) != expected:
        raise ValueError("Summary matrix is incomplete.")
    data_index = {(int(row["patterns"]), int(row["text_length"])): row for row in datasets}
    if set(data_index) != {(k, n) for k in COUNTS for n in LENGTHS}:
        raise ValueError("Dataset metadata is incomplete or duplicated.")
    for k in COUNTS:
        for n in LENGTHS:
            counts = {int(indexed[(algorithm, k, n)]["matches"]) for algorithm in ALGORITHMS}
            if counts != {int(data_index[(k, n)]["matches"])} or next(iter(counts)) <= 0:
                raise ValueError("Algorithms and dataset metadata disagree on matches.")
    environment = {}
    for line in (RESULTS / "environment.txt").read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        environment[key] = value
    return indexed, data_index, environment


def milliseconds(row, field):
    return float(row["avg_" + field + "_ns"]) / 1_000_000


def search_table(summary):
    rows = [["Patterns", "Text length", "AC search, ms", "KMP search, ms", "KMP / AC", "Matches"]]
    for k in COUNTS:
        for n in LENGTHS:
            ac, kmp = (summary[(algorithm, k, n)] for algorithm in ALGORITHMS)
            ratio = float(kmp["avg_search_ns"]) / float(ac["avg_search_ns"])
            rows.append([f"{k:,}", f"{n:,}", f"{milliseconds(ac, 'search'):.4f}",
                         f"{milliseconds(kmp, 'search'):.4f}", f"{ratio:.2f}x", ac["matches"]])
    return rows


def total_table(summary):
    rows = [["Patterns", "Text length", "AC build, ms", "KMP build, ms", "AC total, ms", "KMP total, ms"]]
    for k in COUNTS:
        for n in LENGTHS:
            ac, kmp = (summary[(algorithm, k, n)] for algorithm in ALGORITHMS)
            rows.append([f"{k:,}", f"{n:,}", f"{milliseconds(ac, 'build'):.4f}",
                         f"{milliseconds(kmp, 'build'):.4f}", f"{milliseconds(ac, 'total'):.4f}",
                         f"{milliseconds(kmp, 'total'):.4f}"])
    return rows


def markdown_table(rows):
    return "\n".join(["| " + " | ".join(rows[0]) + " |", "| " + " | ".join("---" for _ in rows[0]) + " |"]
                     + ["| " + " | ".join(row) + " |" for row in rows[1:]])


def discussion(summary, datasets):
    largest_ac = summary[("Aho-Corasick", 1000, 100000)]
    largest_kmp = summary[("KMP", 1000, 100000)]
    ratio = float(largest_kmp["avg_search_ns"]) / float(largest_ac["avg_search_ns"])
    total_ratio = float(largest_kmp["avg_total_ns"]) / float(largest_ac["avg_total_ns"])
    smallest_ac = summary[("Aho-Corasick", 10, 1000)]
    smallest_kmp = summary[("KMP", 10, 1000)]
    winner = "KMP" if float(smallest_kmp["avg_total_ns"]) < float(smallest_ac["avg_total_ns"]) else "Aho-Corasick"
    largest = datasets[(1000, 100000)]
    transition_kib = int(largest["transition_slots"]) * 4 / 1024
    kmp_kib = int(largest["total_pattern_length"]) * 4 / 1024
    return [
        f"For 1,000 patterns and 100,000 text characters, mean search time was "
        f"{milliseconds(largest_ac, 'search'):.4f} ms for Aho-Corasick and "
        f"{milliseconds(largest_kmp, 'search'):.4f} ms for repeated KMP: a {ratio:.2f}x "
        f"search speedup on this input. Including construction, the observed speedup was {total_ratio:.2f}x.",
        f"For the smallest case (10 patterns, 1,000 characters), {winner} had the lower mean "
        f"build-plus-search time. Aho-Corasick took {milliseconds(smallest_ac, 'total'):.4f} ms and "
        f"KMP took {milliseconds(smallest_kmp, 'total'):.4f} ms. Preprocessing therefore matters when "
        f"choosing a matcher for short or one-off searches; a faster scan alone does not establish a faster complete operation.",
        f"The largest case has {int(largest['states']):,} states, alphabet size {largest['alphabet_size']}, "
        f"and {int(largest['transition_slots']):,} transition slots. Their 32-bit integer payload is "
        f"{transition_kib:.1f} KiB; KMP prefix-table integer payload is {kmp_kib:.1f} KiB. These are "
        f"derived payload sizes, not measured heap usage: objects, references, maps, lists, arrays' headers, "
        f"the retained dictionary, and temporary construction allocations add memory.",
        "The broad result is consistent with one shared text scan versus one scan per pattern. "
        "Individual timings need not be monotonic: the cases have different seeds, pattern lengths, "
        "alphabet sizes, and incidental matches, and the JVM and operating system add noise. "
        "These nine inputs and five samples per algorithm are not a statistical guarantee or a worst-case study.",
    ]


def make_chart(summary):
    drawing = Drawing(500, 205)
    x0, width, low, high = 114, 340, -3, 3
    drawing.add(String(0, 192, "Search at 100,000 text characters", fontName="Helvetica-Bold", fontSize=11, fillColor=BLUE))
    drawing.add(String(0, 177, "Mean milliseconds; logarithmic axis; lower is faster", fontSize=8, fillColor=GRAY))
    for power in range(low, high + 1):
        x = x0 + (power - low) * width / (high - low)
        drawing.add(Line(x, 32, x, 161, strokeColor=colors.HexColor("#DEE6EB"), strokeWidth=0.5))
        drawing.add(String(x, 19, f"{10 ** power:g}", textAnchor="middle", fontSize=8, fillColor=GRAY))
    for index, k in enumerate(COUNTS):
        baseline = 143 - index * 43
        drawing.add(String(0, baseline - 4, f"{k:,} patterns", fontSize=9, fillColor=BLUE))
        for offset, algorithm, color in ((0, "Aho-Corasick", TEAL), (-14, "KMP", ORANGE)):
            value = milliseconds(summary[(algorithm, k, 100000)], "search")
            end = x0 + (math.log10(value) - low) * width / (high - low)
            drawing.add(Rect(x0, baseline + offset, max(1, end - x0), 10, fillColor=color, strokeColor=None))
            drawing.add(String(end + 4, baseline + offset + 2, f"{value:.3f}", fontSize=7, fillColor=BLUE))
    drawing.add(Rect(115, 0, 9, 9, fillColor=TEAL, strokeColor=None))
    drawing.add(String(129, 1, "Aho-Corasick", fontSize=8, fillColor=GRAY))
    drawing.add(Rect(220, 0, 9, 9, fillColor=ORANGE, strokeColor=None))
    drawing.add(String(234, 1, "Separate KMP", fontSize=8, fillColor=GRAY))
    return drawing


def write_markdown(summary, datasets, env):
    findings = discussion(summary, datasets)
    experiment = (
        "The full 3 x 3 matrix uses 10, 100, and 1,000 distinct patterns with text lengths of 1,000, "
        "10,000, and 100,000 UTF-16 code units. Patterns have lengths 3-12 and use lowercase Latin "
        "letters. Up to 20 patterns are injected into separate text segments. Every case has a "
        "recorded seed; inputs, exact-match validation, and file output are outside measured intervals. "
        "Before measurement there are 100 global warm-up rounds and 20 per case. Exactly five runs "
        "of each algorithm use System.nanoTime(). Run order alternates. Each run builds one matcher "
        "and searches one text. Both algorithms enumerate all matches through the same counting "
        "callback; they do not allocate a match list in the timed search. Arithmetic means use raw "
        "nanosecond values before rounding."
    )
    complexity = [
        ["Operation", "Aho-Corasick (this implementation)", "Repeated KMP"],
        ["Preprocessing", "Expected O(M + S * sigma + k)", "O(M + k)"],
        ["Search", "Expected O(n + z)", "O(k * n + z)"],
        ["Matcher auxiliary space", "O(S * (sigma + 1) + k + sigma)", "O(M + k)"],
        ["Streaming search extra space", "O(1)", "O(1)"],
        ["Collecting all matches", "Additional O(z)", "Additional O(z)"],
    ]
    results_md = "\n\n".join([
        "# Experimental results", "All timings below are real local measurements, not estimates.",
        experiment, "## Search time", markdown_table(search_table(summary)),
        "KMP / AC is the ratio of mean search times, not the mean of per-run ratios. A value above 1 favors Aho-Corasick.",
        "![Measured search times, logarithmic axis](search-comparison.svg)",
        "## Construction and one complete operation", markdown_table(total_table(summary)),
        "Total is construction plus one search. All times are milliseconds and each cell is a five-run arithmetic mean.",
        "## Interpretation", *findings,
        "## Evidence", "- [90 raw measured runs](benchmark-runs.csv)\n- [18 unrounded-to-milliseconds summaries, with search minima/maxima](benchmark-summary.csv)\n- [9 dataset seeds and automaton sizes](datasets.csv)\n- [Execution environment](environment.txt)\n- [Correctness verification](verification.txt)",
    ]) + "\n"
    (RESULTS / "RESULTS.md").write_text(results_md, encoding="utf-8")
    report = "\n\n".join([
        "# Aho-Corasick Algorithm: Implementation and Experimental Comparison with KMP",
        "Sultanali Baltabay | 14 November 2026 | Java bonus task",
        "> AI-assisted technical report. This document does not replace the separate handwritten page, which must be written independently in the student's own words.",
        "## 1. Objective", "Implement Aho-Corasick in Java, find all occurrences of multiple patterns, "
        "and compare its build and search times with KMP run separately for each pattern. Evaluate "
        "the entire required input matrix with five measured repetitions and analyze time and space.",
        "## 2. Implementation", "The trie shares pattern prefixes. Terminal nodes retain original pattern IDs, "
        "including duplicate entries. Failure links are constructed by breadth-first traversal and identify "
        "the longest proper suffix that is also a trie prefix. Missing transitions are completed using "
        "the failure state. Output links point to the nearest terminal failure ancestor, avoiding inherited "
        "output-list copies. The search scans the text once, emitting terminal IDs and suffix outputs. "
        "The algorithm follows the finite-state approach introduced by Aho and Corasick [1].",
        "The compressed alphabet contains the dictionary's distinct UTF-16 code units. Each state "
        "has a dense array over that alphabet; an unknown symbol resets the search to the root. "
        "Matching is exact and case-sensitive, with zero-based half-open UTF-16 offsets. Empty "
        "patterns are rejected. Empty texts and dictionaries return no results. The matcher is reusable.",
        "For text `ahishers` and patterns `[he, she, his, hers]`, matches are `his [1,4)`, "
        "`she [3,6)`, `he [4,6)`, and `hers [4,8)`. The `he` match follows the output link "
        "from the `she` state. Overlapping matches are preserved.",
        "The separate KMP implementation builds one prefix table per pattern and scans the full "
        "text for each pattern. After reporting a match it follows the last prefix value to preserve overlaps.",
        "## 3. Correctness", "The recorded run passed 3,108 assertions: 14 named input cases, "
        "explicit expected positions and counts, invalid-input and API checks, and 500 seeded random "
        "cases checked against an independent naive substring oracle. Coverage includes suffix outputs, "
        "overlaps, duplicates, Unicode, empty inputs, unknown characters, and repeated searches. "
        "Exact positions and pattern IDs are also compared between both algorithms for every benchmark input.",
        "## 4. Methodology", experiment,
        f"Recorded environment: {env['os.name']} {env['os.arch']}, {env['available_processors']} "
        f"available logical processors; {env['java.vendor']} Java {env['java.version']}; "
        f"{env['java.vm.name']}. CPU identifier: {env['processor']}. "
        f"Recorded timestamp: {env['experiment_time']}.",
        "## 5. Complexity", "Let k be the pattern count, M the total pattern length, S <= M + 1 the trie "
        "state count, sigma the distinct dictionary-symbol count, n the text length, and z the number "
        "of emitted occurrences. Alphabet-map lookups use expected constant time.",
        markdown_table(complexity),
        "The dense completed-transition table explains the S * sigma term. With a fixed alphabet, "
        "construction and matcher storage are linear in M + k. Output links store only O(k) direct "
        "terminal IDs instead of copying suffix outputs into descendants. The BFS queue requires "
        "O(S) temporary construction space. Add O(M) if retained dictionary characters are counted "
        "and O(n) for the input text itself. Build plus one search is expected O(M + S * sigma + k + n + z) "
        "for Aho-Corasick and O(M + k + k * n + z) for repeated KMP.",
        "## 6. Measured results", markdown_table(search_table(summary)),
        "Search values are arithmetic means in milliseconds; KMP / AC divides the two means. "
        "All occurrences are enumerated, but full match objects are not materialized inside the timed section.",
        "![Measured comparison](../results/search-comparison.svg)", markdown_table(total_table(summary)),
        "Total means construction plus one search. Minima, maxima, and all five individual "
        "measurements are retained in the summary and raw CSV files.",
        "## 7. Interpretation and limitations", *findings,
        "Aho-Corasick is well suited to many fixed patterns and repeated text searches because "
        "the automaton shares prefixes and the text scan. KMP offers simpler preprocessing and "
        "smaller tables for one or a few patterns. Dense transition arrays become expensive for a "
        "large alphabet; rebuilding is required when the dictionary changes. Both approaches are "
        "exact-match algorithms and must account for output size when matches are frequent.",
        "Only a single JVM process and five measured repetitions per case were used. Global and "
        "per-case warm-up reduce, but do not remove, JIT effects. Garbage collection, OS scheduling, "
        "CPU power management, and workload-dependent match density affect timings. There are no "
        "confidence intervals and no measured heap-profile results. The data support this local "
        "comparison, not a universal speedup claim.",
        "## 8. Reproduction and submission", "Run `powershell -ExecutionPolicy Bypass -File "
        ".\\scripts\\run.ps1 all` on Windows, or `bash scripts/run.sh all` on Linux/macOS with "
        "JDK 17+. Run `python scripts/build_report.py` with ReportLab and pypdf installed to "
        "regenerate this report after new measurements. Java has no third-party dependencies. "
        "Submit the GitHub repository URL through Moodle and independently prepare the required handwritten page.",
        "## References", "[1] A. V. Aho and M. J. Corasick. Efficient String Matching: An Aid to "
        "Bibliographic Search. Communications of the ACM, 18(6), 333-340, 1975. "
        "[Original paper](https://cr.yp.to/bib/1975/aho.pdf); "
        "[DOI](https://doi.org/10.1145/360825.360855).",
        "[2] Oracle. Java SE 25: System.nanoTime(). "
        "[API documentation](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/System.html#nanoTime()). "
        "Use differences for elapsed time; nanosecond units do not imply nanosecond accuracy.",
    ]) + "\n"
    (DOCS / "REPORT.md").write_text(report, encoding="utf-8")
    return experiment, complexity, findings


def build_pdf(summary, datasets, env, chart, experiment, complexity, findings):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TitleCustom", fontName="Helvetica-Bold", fontSize=27, leading=31, textColor=BLUE, spaceAfter=12))
    styles.add(ParagraphStyle("SubtitleCustom", fontName="Helvetica", fontSize=10, leading=15, textColor=GRAY, spaceAfter=15))
    styles.add(ParagraphStyle("HeadingCustom", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=BLUE, spaceBefore=14, spaceAfter=7))
    styles.add(ParagraphStyle("BodyCustom", fontName="Helvetica", fontSize=9.3, leading=13.8, textColor=BLUE, spaceAfter=8))
    styles.add(ParagraphStyle("SmallCustom", fontName="Helvetica", fontSize=8, leading=11.4, textColor=GRAY, spaceAfter=7))
    styles.add(ParagraphStyle("TableCell", fontName="Helvetica", fontSize=8, leading=11, textColor=BLUE))
    styles.add(ParagraphStyle("TableHeader", fontName="Helvetica-Bold", fontSize=7.7, leading=10.5, textColor=colors.white))
    story = []

    def paragraph(text, style="BodyCustom"):
        return Paragraph(text, styles[style])

    def heading(text):
        story.append(paragraph(text, "HeadingCustom"))

    def body(text):
        story.append(paragraph(escape(text)))

    def table(rows, widths=None):
        cells = [[paragraph(escape(str(cell)), "TableHeader" if index == 0 else "TableCell")
                  for cell in row] for index, row in enumerate(rows)]
        item = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        item.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
            ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.HexColor("#CAD7DF")),
        ]))
        story.append(item)
        story.append(Spacer(1, 8))

    story.append(paragraph("Aho-Corasick<br/>Algorithm", "TitleCustom"))
    story.append(paragraph("Implementation and experimental comparison with separate KMP searches<br/>"
                           "Sultanali Baltabay | Java bonus task | 14 November 2026", "SubtitleCustom"))
    note = paragraph("<b>AI-assisted technical report.</b> The assignment's separate handwritten page "
                     "must be written independently in the student's own words. This report does not replace it.", "SmallCustom")
    notice = Table([[note]], colWidths=[500])
    notice.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE),
                               ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CAD7DF")),
                               ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8)]))
    story.append(notice)
    heading("1. Objective and implementation")
    body("Implement multi-pattern matching in Java, report all occurrences, and compare Aho-Corasick "
         "with KMP run separately for each pattern over the required nine input combinations.")
    for title, description in [
        ("Trie", "Insert all patterns and share common prefixes. Terminal nodes retain original pattern IDs, including duplicate strings."),
        ("Failure links", "Use breadth-first traversal. Each link identifies the longest proper suffix of a state's prefix that is also a trie prefix. Root children fail to the root."),
        ("Output links", "Point to the nearest terminal failure ancestor. Follow this chain to emit suffix matches without copying inherited output lists."),
        ("Completed transitions", "Fill missing transitions from the failure state during BFS. Search makes one transition per known text symbol; unknown symbols reset to the root."),
    ]:
        story.append(paragraph(f"<b>{title}.</b> {escape(description)}"))
    body("Exact matching is case-sensitive and includes overlaps. Positions are zero-based UTF-16 "
         "code-unit offsets with exclusive ends. Empty patterns are rejected; empty text or dictionary "
         "returns no matches. The automaton can be reused. The approach follows Aho and Corasick [1].")
    heading("Worked example")
    body("For text ahishers and patterns [he, she, his, hers], the output is:")
    table([["Pattern", "Pattern ID", "Range [start, end)"], ["his", "2", "[1, 4)"],
           ["she", "1", "[3, 6)"], ["he", "0", "[4, 6)"], ["hers", "3", "[4, 8)"]], [170, 120, 210])
    body("At she, the output link reports he as well. The start index is endExclusive minus pattern length.")
    heading("Correctness evidence")
    body("3,108 assertions passed: 14 named cases, explicit expected positions/counts, API validation, "
         "and 500 seeded random cases checked against a naive oracle. Coverage includes suffixes, "
         "overlaps, duplicates, Unicode/emoji, deep fallback, unknown symbols, and matcher reuse. "
         "Both algorithms' exact match IDs and positions also agree for all nine benchmark inputs.")

    story.append(PageBreak())
    heading("2. Experiment design")
    body(experiment)
    body("Aho-Corasick uses a compressed alphabet with a dense transition array in each state. "
         "KMP builds one prefix table per pattern and scans the full text separately for each. "
         "Its post-match fallback preserves overlapping occurrences.")
    heading("Recorded environment")
    table([["Property", "Recorded value"], ["Operating system", f"{env['os.name']} {env['os.arch']}"],
           ["Java", f"{env['java.vendor']} {env['java.version']}"], ["Virtual machine", env['java.vm.name']],
           ["Logical processors", env['available_processors']], ["CPU identifier", env['processor']],
           ["Timestamp", env['experiment_time']]], [125, 375])
    heading("3. Time and space complexity")
    body("k = patterns; M = total pattern length; S <= M + 1 = trie states; sigma = distinct "
         "dictionary symbols; n = text length; z = emitted occurrences. Hash-map alphabet lookup is expected O(1).")
    table(complexity, [125, 235, 140])
    body("The dense completed transitions explain S * sigma. With a fixed alphabet, construction "
         "and matcher storage are linear in M + k. Direct output IDs use O(k); output links avoid "
         "inherited-list duplication. The BFS queue adds O(S) temporary construction space. Add "
         "O(M) for dictionary characters if included, and O(n) for the input text.")
    body("Build plus one search: expected O(M + S * sigma + k + n + z) for Aho-Corasick; "
         "O(M + k + k * n + z) for repeated KMP. A large output necessarily adds reporting work.")

    story.append(PageBreak())
    heading("4. Search results")
    body("Mean search time across five runs, in milliseconds. KMP / AC is the ratio of the two "
         "means; above 1 favors Aho-Corasick. Every occurrence is enumerated through the shared "
         "callback. Input generation and validation are excluded.")
    table(search_table(summary), [58, 76, 96, 100, 83, 87])
    story.append(Spacer(1, 12))
    story.append(chart)
    heading("Observed behavior")
    body(findings[0])
    body(findings[3])
    body("Each case has its own seeded dictionary; pattern lengths, alphabet sizes, and incidental "
         "matches can vary across text sizes. Search minima/maxima and all individual observations "
         "are preserved in the committed CSV files.")

    story.append(PageBreak())
    heading("5. Construction and total execution time")
    body("Five-run means in milliseconds. Total = one construction + one search in the same run. "
         "This separates automaton setup from the benefit of reusing it across searches.")
    table(total_table(summary), [58, 76, 90, 92, 92, 92])
    heading("Tradeoffs and limitations")
    body(findings[1])
    body(findings[2])
    body("Aho-Corasick shares prefixes and scans the text once, making it attractive for many fixed "
         "patterns. KMP has cheaper setup and smaller tables for a single or small pattern set. "
         "Dense arrays can be costly for large alphabets. A changed dictionary requires a new automaton.")
    body("This experiment uses one JVM process and five samples per case. Warm-up reduces but does "
         "not eliminate JIT effects. OS scheduling, CPU power management, and garbage collection "
         "still affect results. No confidence interval, worst-case performance guarantee, or measured "
         "heap profile is claimed.")
    heading("6. Reproduction and submission")
    body("Use JDK 17+. On Windows, run powershell -ExecutionPolicy Bypass -File .\\scripts\\run.ps1 all. "
         "On Linux/macOS, run bash scripts/run.sh all. The Java project needs no third-party libraries. "
         "The optional Python report builder validates the CSV files and regenerates the reports.")
    body("Submit the repository URL through Moodle and write the required handwritten page independently. "
         "README.md maps each requirement to its implementation and evidence.")
    heading("References")
    story.append(paragraph('[1] A. V. Aho and M. J. Corasick. Efficient String Matching: An Aid to Bibliographic Search. '
                           'CACM 18(6), 333-340, 1975. <link href="https://doi.org/10.1145/360825.360855" color="#00877F">'
                           'doi:10.1145/360825.360855</link>.', "SmallCustom"))
    story.append(paragraph('[2] Oracle, Java SE 25, <link href="https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/System.html#nanoTime()" color="#00877F">'
                           'System.nanoTime()</link>. Subtract readings for elapsed time; nanosecond units do not guarantee nanosecond accuracy.', "SmallCustom"))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CAD7DF"))
        canvas.line(46, 36, A4[0] - 46, 36)
        canvas.setFillColor(GRAY)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(46, 24, "Sultanali Baltabay | Aho-Corasick and KMP | Technical report")
        canvas.drawRightString(A4[0] - 46, 24, str(document.page))
        canvas.restoreState()

    PDF.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(PDF), pagesize=A4, rightMargin=46, leftMargin=46,
                                 topMargin=35, bottomMargin=49, title="Aho-Corasick: Java Implementation and KMP Comparison",
                                 author="Sultanali Baltabay", subject="AI-assisted technical experiment report")
    document.build(story, onFirstPage=footer, onLaterPages=footer)


def main():
    summary, datasets, env = load_and_validate()
    DOCS.mkdir(exist_ok=True)
    chart = make_chart(summary)
    renderSVG.drawToFile(chart, str(RESULTS / "search-comparison.svg"))
    experiment, complexity, findings = write_markdown(summary, datasets, env)
    build_pdf(summary, datasets, env, chart, experiment, complexity, findings)
    from pypdf import PdfReader
    reader = PdfReader(PDF)
    text = "\n".join(page.extract_text() for page in reader.pages)
    if len(reader.pages) != 4 or "3,108" not in text or "100,000" not in text:
        raise ValueError(f"Unexpected PDF page count or missing content: {len(reader.pages)} pages")
    print("Validated 90 runs, 18 averages, 9 datasets, and matching count/time invariants.")
    print("Generated docs/REPORT.md, results/RESULTS.md, results/search-comparison.svg, and a four-page PDF.")


if __name__ == "__main__":
    main()
