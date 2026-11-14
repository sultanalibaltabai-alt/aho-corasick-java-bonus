package edu.algorithms.matching;

/** Receives one occurrence without requiring a Match object to be allocated. */
@FunctionalInterface
public interface MatchConsumer {
    void accept(int patternId, int startInclusive, int endExclusive);
}
