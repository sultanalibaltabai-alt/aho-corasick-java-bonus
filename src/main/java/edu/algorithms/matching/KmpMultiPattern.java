package edu.algorithms.matching;

import java.util.List;
import java.util.Objects;

/** Runs KMP separately for every pattern, retaining each prefix table for reuse. */
public final class KmpMultiPattern implements MultiPatternMatcher {
    private final List<String> patterns;
    private final int[][] prefixTables;

    public KmpMultiPattern(List<String> patterns) {
        this.patterns = PatternInputs.validatedCopy(patterns);
        prefixTables = new int[this.patterns.size()][];
        for (int id = 0; id < this.patterns.size(); id++) {
            prefixTables[id] = buildPrefixTable(this.patterns.get(id));
        }
    }

    @Override
    public List<String> patterns() {
        return patterns;
    }

    @Override
    public void forEachMatch(String text, MatchConsumer consumer) {
        Objects.requireNonNull(text, "text");
        Objects.requireNonNull(consumer, "consumer");
        for (int id = 0; id < patterns.size(); id++) {
            searchPattern(text, id, consumer);
        }
    }

    private void searchPattern(String text, int patternId, MatchConsumer consumer) {
        String pattern = patterns.get(patternId);
        int[] prefix = prefixTables[patternId];
        int matched = 0;
        for (int index = 0; index < text.length(); index++) {
            while (matched > 0 && text.charAt(index) != pattern.charAt(matched)) {
                matched = prefix[matched - 1];
            }
            if (text.charAt(index) == pattern.charAt(matched)) {
                matched++;
            }
            if (matched == pattern.length()) {
                consumer.accept(patternId, index + 1 - matched, index + 1);
                matched = prefix[matched - 1];
            }
        }
    }

    private static int[] buildPrefixTable(String pattern) {
        int[] prefix = new int[pattern.length()];
        int matched = 0;
        for (int index = 1; index < pattern.length(); index++) {
            while (matched > 0 && pattern.charAt(index) != pattern.charAt(matched)) {
                matched = prefix[matched - 1];
            }
            if (pattern.charAt(index) == pattern.charAt(matched)) {
                matched++;
            }
            prefix[index] = matched;
        }
        return prefix;
    }
}
