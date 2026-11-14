package edu.algorithms.matching;

import java.util.Arrays;
import java.util.List;

public final class Demo {
    private Demo() {
    }

    public static void main(String[] args) {
        if (args.length == 1) {
            throw new IllegalArgumentException("Usage: Demo [text pattern1 pattern2 ...]");
        }
        String text = args.length == 0 ? "ahishers" : args[0];
        List<String> patterns = args.length == 0
                ? List.of("he", "she", "his", "hers")
                : List.copyOf(Arrays.asList(args).subList(1, args.length));
        MultiPatternMatcher matcher = new AhoCorasick(patterns);
        System.out.println("Text: " + text);
        System.out.println("Patterns: " + patterns);
        for (Match match : matcher.findAll(text)) {
            System.out.printf("pattern[%d]=%s at [%d, %d)%n", match.patternId(),
                    patterns.get(match.patternId()), match.startInclusive(), match.endExclusive());
        }
    }
}
