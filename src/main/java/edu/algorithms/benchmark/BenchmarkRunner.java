package edu.algorithms.benchmark;

import edu.algorithms.matching.AhoCorasick;
import edu.algorithms.matching.KmpMultiPattern;
import edu.algorithms.matching.Match;
import edu.algorithms.matching.MultiPatternMatcher;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.function.Supplier;

public final class BenchmarkRunner {
    private static final int[] PATTERN_COUNTS = {10, 100, 1_000};
    private static final int[] TEXT_LENGTHS = {1_000, 10_000, 100_000};
    private static final int REPETITIONS = 5;
    private static final int WARMUP_ROUNDS = 20;
    private static final int GLOBAL_WARMUP_ROUNDS = 100;
    private static volatile long blackhole;

    private BenchmarkRunner() {
    }

    public static void main(String[] args) throws IOException {
        Path output = args.length == 0 ? Path.of("results") : Path.of(args[0]);
        Files.createDirectories(output);
        warmUpJvm();
        List<Measurement> measurements = new ArrayList<>();
        List<String> datasetRows = new ArrayList<>();
        datasetRows.add("patterns,text_length,seed,total_pattern_length,states,alphabet_size,transition_slots,matches");
        for (int patternCount : PATTERN_COUNTS) {
            for (int textLength : TEXT_LENGTHS) {
                BenchmarkDataset dataset = BenchmarkDataset.generate(patternCount, textLength);
                AhoCorasick automaton = new AhoCorasick(dataset.patterns());
                KmpMultiPattern kmp = new KmpMultiPattern(dataset.patterns());
                verifyEquivalentMatches(automaton, kmp, dataset.text());
                Supplier<MultiPatternMatcher> ahoFactory = () -> new AhoCorasick(dataset.patterns());
                Supplier<MultiPatternMatcher> kmpFactory = () -> new KmpMultiPattern(dataset.patterns());
                for (int warmup = 0; warmup < WARMUP_ROUNDS; warmup++) {
                    blackhole = ahoFactory.get().countMatches(dataset.text());
                    blackhole = kmpFactory.get().countMatches(dataset.text());
                }
                long expectedCount = automaton.countMatches(dataset.text());
                for (int run = 1; run <= REPETITIONS; run++) {
                    if (run % 2 == 1) {
                        measurements.add(measure("Aho-Corasick", dataset, run, ahoFactory, expectedCount));
                        measurements.add(measure("KMP", dataset, run, kmpFactory, expectedCount));
                    } else {
                        measurements.add(measure("KMP", dataset, run, kmpFactory, expectedCount));
                        measurements.add(measure("Aho-Corasick", dataset, run, ahoFactory, expectedCount));
                    }
                }
                int totalLength = dataset.patterns().stream().mapToInt(String::length).sum();
                datasetRows.add(String.format(Locale.ROOT, "%d,%d,%d,%d,%d,%d,%d,%d",
                        patternCount, textLength, dataset.seed(), totalLength, automaton.stateCount(),
                        automaton.alphabetSize(), automaton.transitionSlotCount(), expectedCount));
                System.out.printf("Verified and measured: patterns=%d, text=%d, matches=%d%n",
                        patternCount, textLength, expectedCount);
            }
        }
        writeMeasurements(output, measurements);
        Files.write(output.resolve("datasets.csv"), datasetRows, StandardCharsets.UTF_8);
        writeEnvironment(output);
        System.out.println("Saved 90 measured runs and 18 averages to " + output.toAbsolutePath());
    }

    private static void warmUpJvm() {
        System.out.println("Warming up the JVM before the first measured case...");
        BenchmarkDataset dataset = BenchmarkDataset.generate(1_000, 10_000);
        for (int round = 0; round < GLOBAL_WARMUP_ROUNDS; round++) {
            blackhole = new AhoCorasick(dataset.patterns()).countMatches(dataset.text());
            blackhole = new KmpMultiPattern(dataset.patterns()).countMatches(dataset.text());
        }
    }

    private static Measurement measure(String algorithm, BenchmarkDataset dataset, int run,
                                       Supplier<MultiPatternMatcher> factory, long expectedCount) {
        long start = System.nanoTime();
        MultiPatternMatcher matcher = factory.get();
        long built = System.nanoTime();
        long count = matcher.countMatches(dataset.text());
        long finished = System.nanoTime();
        blackhole = count;
        if (count != expectedCount) {
            throw new IllegalStateException("Measured search returned a different match count.");
        }
        return new Measurement(algorithm, dataset.patterns().size(), dataset.text().length(), run,
                built - start, finished - built, finished - start, count);
    }

    private static void verifyEquivalentMatches(MultiPatternMatcher first, MultiPatternMatcher second,
                                                String text) {
        Comparator<Match> order = Comparator.comparingInt(Match::patternId)
                .thenComparingInt(Match::startInclusive).thenComparingInt(Match::endExclusive);
        List<Match> left = first.findAll(text).stream().sorted(order).toList();
        List<Match> right = second.findAll(text).stream().sorted(order).toList();
        if (!left.equals(right)) {
            throw new IllegalStateException("The algorithms disagree on exact match identities or positions.");
        }
    }

    private static void writeMeasurements(Path output, List<Measurement> measurements) throws IOException {
        List<String> raw = new ArrayList<>();
        raw.add("algorithm,patterns,text_length,run,build_ns,search_ns,total_ns,matches");
        for (Measurement row : measurements) {
            raw.add(String.format(Locale.ROOT, "%s,%d,%d,%d,%d,%d,%d,%d", row.algorithm(),
                    row.patternCount(), row.textLength(), row.run(), row.buildNs(), row.searchNs(),
                    row.totalNs(), row.matches()));
        }
        Files.write(output.resolve("benchmark-runs.csv"), raw, StandardCharsets.UTF_8);
        List<String> summary = new ArrayList<>();
        summary.add("algorithm,patterns,text_length,runs,avg_build_ns,avg_search_ns,avg_total_ns,min_search_ns,max_search_ns,matches");
        for (int patternCount : PATTERN_COUNTS) {
            for (int textLength : TEXT_LENGTHS) {
                for (String algorithm : List.of("Aho-Corasick", "KMP")) {
                    List<Measurement> group = measurements.stream().filter(row ->
                            row.patternCount() == patternCount && row.textLength() == textLength
                                    && row.algorithm().equals(algorithm)).toList();
                    summary.add(String.format(Locale.ROOT, "%s,%d,%d,%d,%.1f,%.1f,%.1f,%d,%d,%d",
                            algorithm, patternCount, textLength, group.size(),
                            group.stream().mapToLong(Measurement::buildNs).average().orElseThrow(),
                            group.stream().mapToLong(Measurement::searchNs).average().orElseThrow(),
                            group.stream().mapToLong(Measurement::totalNs).average().orElseThrow(),
                            group.stream().mapToLong(Measurement::searchNs).min().orElseThrow(),
                            group.stream().mapToLong(Measurement::searchNs).max().orElseThrow(),
                            group.get(0).matches()));
                }
            }
        }
        Files.write(output.resolve("benchmark-summary.csv"), summary, StandardCharsets.UTF_8);
    }

    private static void writeEnvironment(Path output) throws IOException {
        List<String> lines = new ArrayList<>();
        lines.add("experiment_time=" + ZonedDateTime.now(ZoneId.of("Asia/Qyzylorda")));
        for (String key : List.of("java.version", "java.vendor", "java.vm.name", "os.name", "os.version", "os.arch")) {
            lines.add(key + "=" + System.getProperty(key));
        }
        lines.add("available_processors=" + Runtime.getRuntime().availableProcessors());
        lines.add("processor=" + System.getenv().getOrDefault("PROCESSOR_IDENTIFIER", "unknown"));
        lines.add("warmup_rounds_per_case=" + WARMUP_ROUNDS);
        lines.add("global_warmup_rounds=" + GLOBAL_WARMUP_ROUNDS);
        lines.add("global_warmup_input=1000 patterns, 10000 characters");
        lines.add("measured_runs_per_algorithm_per_case=" + REPETITIONS);
        lines.add("timer=System.nanoTime()");
        lines.add("timed_search=shared countMatches callback enumerates all occurrences; no match list allocation");
        lines.add("input_generation_and_exact_result_validation=outside measured intervals");
        lines.add("total_ns=build_ns+search_ns (one construction plus one search per run)");
        lines.add("gc_policy=no explicit System.gc(); allocation and incidental GC can affect measured times");
        Files.write(output.resolve("environment.txt"), lines, StandardCharsets.UTF_8);
    }

    private record Measurement(String algorithm, int patternCount, int textLength, int run,
                               long buildNs, long searchNs, long totalNs, long matches) {
    }
}
