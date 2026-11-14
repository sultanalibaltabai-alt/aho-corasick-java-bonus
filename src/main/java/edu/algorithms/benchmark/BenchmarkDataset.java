package edu.algorithms.benchmark;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Random;
import java.util.Set;

record BenchmarkDataset(List<String> patterns, String text, long seed) {
    static BenchmarkDataset generate(int patternCount, int textLength) {
        long seed = 20261114L + 1_000_003L * patternCount + textLength;
        Random random = new Random(seed);
        Set<String> distinct = new LinkedHashSet<>();
        while (distinct.size() < patternCount) {
            distinct.add(randomString(random, 3 + random.nextInt(10)));
        }
        List<String> patterns = List.copyOf(new ArrayList<>(distinct));
        char[] text = randomString(random, textLength).toCharArray();
        int injected = Math.min(20, patternCount);
        int segmentLength = textLength / injected;
        for (int index = 0; index < injected; index++) {
            String pattern = patterns.get(index);
            int start = index * segmentLength;
            pattern.getChars(0, pattern.length(), text, start);
        }
        return new BenchmarkDataset(patterns, new String(text), seed);
    }

    private static String randomString(Random random, int length) {
        StringBuilder value = new StringBuilder(length);
        for (int index = 0; index < length; index++) {
            value.append((char) ('a' + random.nextInt(26)));
        }
        return value.toString();
    }
}
