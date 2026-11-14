package edu.algorithms.matching;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Random;

public final class CorrectnessTests {
    private static int assertions;
    private static final Comparator<Match> ORDER = Comparator.comparingInt(Match::patternId)
            .thenComparingInt(Match::startInclusive).thenComparingInt(Match::endExclusive);

    private CorrectnessTests() {
    }

    public static void main(String[] args) {
        checkCase("classic failure/output example", List.of("he", "she", "his", "hers"), "ahishers");
        checkCase("suffix output links", List.of("a", "ba", "cba", "dcba"), "dcba");
        checkCase("overlapping nested patterns", List.of("a", "aa", "aaa", "aaaa"), "aaaaa");
        checkCase("overlapping nontrivial prefix", List.of("aba", "ababa", "bab"), "ababababa");
        checkCase("duplicate pattern IDs", List.of("aba", "aba", "ba"), "ababa");
        checkCase("empty text", List.of("a", "ab"), "");
        checkCase("empty dictionary", List.of(), "any text");
        checkCase("no matches", List.of("abc", "def"), "zzzzzz");
        checkCase("patterns longer than text", List.of("abcdef", "abcde"), "ab");
        checkCase("unknown characters reset state", List.of("ab", "b"), "a#bab#b");
        checkCase("boundaries and case", List.of("Ab", "ab", "b"), "Ab ab");
        checkCase("Unicode UTF-16 positions", List.of("кот", "от", "猫", "😀", "😀猫"), "кот😀猫кот");
        checkCase("deep fallback", List.of("abcd", "bcd", "cd", "d", "abce"), "abcfabcdabce");
        checkCase("embedded zero code unit", List.of("\u0000a", "a\u0000"), "\u0000a\u0000a");
        checkKnownPositions();
        checkValidation();
        checkDefensiveCopyAndReuse();
        Random random = new Random(20261114L);
        for (int trial = 0; trial < 500; trial++) {
            List<String> patterns = new ArrayList<>();
            int count = random.nextInt(14);
            for (int index = 0; index < count; index++) {
                patterns.add(randomString(random, 1 + random.nextInt(9)));
            }
            checkCase(null, patterns, randomString(random, random.nextInt(90)));
        }
        System.out.printf("PASS: 14 named input cases, API/position checks, 500 seeded random cases; %d assertions.%n",
                assertions);
    }

    private static void checkCase(String name, List<String> patterns, String text) {
        List<Match> expected = sorted(naive(patterns, text));
        for (MultiPatternMatcher matcher : List.of(new AhoCorasick(patterns), new KmpMultiPattern(patterns))) {
            equal(expected, sorted(matcher.findAll(text)), "exact positions for " + name);
            equal((long) expected.size(), matcher.countMatches(text), "count for " + name);
            List<Match> streamed = new ArrayList<>();
            matcher.forEachMatch(text, (id, start, end) -> streamed.add(new Match(id, start, end)));
            equal(expected, sorted(streamed), "streamed positions for " + name);
        }
        if (name != null) {
            System.out.println("PASS: " + name);
        }
    }

    private static void checkKnownPositions() {
        List<Match> expected = List.of(new Match(0, 4, 6), new Match(1, 3, 6),
                new Match(2, 1, 4), new Match(3, 4, 8));
        equal(sorted(expected), sorted(new AhoCorasick(List.of("he", "she", "his", "hers")).findAll("ahishers")),
                "manually verified classic positions");
        equal(9L, new AhoCorasick(List.of("a", "aa", "aaa")).countMatches("aaaa"),
                "manually verified overlapping count");
    }

    private static void checkValidation() {
        expectThrows(NullPointerException.class, () -> new AhoCorasick(null));
        expectThrows(NullPointerException.class, () -> new KmpMultiPattern(null));
        List<String> withNull = new ArrayList<>();
        withNull.add(null);
        expectThrows(NullPointerException.class, () -> new AhoCorasick(withNull));
        expectThrows(NullPointerException.class, () -> new KmpMultiPattern(withNull));
        expectThrows(IllegalArgumentException.class, () -> new AhoCorasick(List.of("")));
        expectThrows(IllegalArgumentException.class, () -> new KmpMultiPattern(List.of("")));
        for (MultiPatternMatcher matcher : List.of(new AhoCorasick(List.of("a")), new KmpMultiPattern(List.of("a")))) {
            expectThrows(NullPointerException.class, () -> matcher.findAll(null));
            expectThrows(NullPointerException.class, () -> matcher.forEachMatch("a", null));
        }
    }

    private static void checkDefensiveCopyAndReuse() {
        for (boolean useAho : List.of(true, false)) {
            List<String> original = new ArrayList<>(List.of("a", "ba"));
            MultiPatternMatcher matcher = useAho ? new AhoCorasick(original) : new KmpMultiPattern(original);
            original.clear();
            equal(List.of("a", "ba"), matcher.patterns(), "defensive dictionary copy");
            equal(2L, matcher.countMatches("ba"), "first search");
            equal(0L, matcher.countMatches("z"), "independent repeated search");
            equal(2L, matcher.countMatches("ba"), "reused search");
            expectThrows(UnsupportedOperationException.class, () -> matcher.patterns().add("x"));
            expectThrows(UnsupportedOperationException.class, () -> matcher.findAll("ba").clear());
        }
    }

    private static List<Match> naive(List<String> patterns, String text) {
        List<Match> matches = new ArrayList<>();
        for (int id = 0; id < patterns.size(); id++) {
            String pattern = patterns.get(id);
            for (int start = 0; start + pattern.length() <= text.length(); start++) {
                if (text.startsWith(pattern, start)) {
                    matches.add(new Match(id, start, start + pattern.length()));
                }
            }
        }
        return matches;
    }

    private static List<Match> sorted(List<Match> matches) {
        return matches.stream().sorted(ORDER).toList();
    }

    private static String randomString(Random random, int length) {
        StringBuilder value = new StringBuilder(length);
        for (int index = 0; index < length; index++) {
            value.append((char) ('a' + random.nextInt(4)));
        }
        return value.toString();
    }

    private static void equal(Object expected, Object actual, String description) {
        assertions++;
        if (!expected.equals(actual)) {
            throw new AssertionError(description + ": expected=" + expected + ", actual=" + actual);
        }
    }

    private static void expectThrows(Class<? extends Throwable> expected, Runnable action) {
        assertions++;
        try {
            action.run();
        } catch (Throwable exception) {
            if (expected.isInstance(exception)) {
                return;
            }
            throw new AssertionError("Expected " + expected.getName() + ", got " + exception, exception);
        }
        throw new AssertionError("Expected " + expected.getName());
    }
}
