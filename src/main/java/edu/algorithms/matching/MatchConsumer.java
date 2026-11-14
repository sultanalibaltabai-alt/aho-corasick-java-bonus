package edu.algorithms.matching;

@FunctionalInterface
public interface MatchConsumer {
    void accept(int patternId, int startInclusive, int endExclusive);
}
