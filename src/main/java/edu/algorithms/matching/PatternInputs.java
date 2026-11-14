package edu.algorithms.matching;

import java.util.List;
import java.util.Objects;

final class PatternInputs {
    private PatternInputs() {
    }

    static List<String> validatedCopy(List<String> patterns) {
        Objects.requireNonNull(patterns, "patterns");
        List<String> copy = List.copyOf(patterns);
        for (String pattern : copy) {
            if (pattern.isEmpty()) {
                throw new IllegalArgumentException("Empty patterns are not supported.");
            }
        }
        return copy;
    }
}
