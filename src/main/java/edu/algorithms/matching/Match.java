package edu.algorithms.matching;

/** A match identified by the original pattern index and a half-open UTF-16 range. */
public record Match(int patternId, int startInclusive, int endExclusive) {
}
