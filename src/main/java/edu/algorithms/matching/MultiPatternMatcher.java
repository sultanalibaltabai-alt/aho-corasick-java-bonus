package edu.algorithms.matching;

import java.util.ArrayList;
import java.util.List;

public interface MultiPatternMatcher {
    List<String> patterns();

    void forEachMatch(String text, MatchConsumer consumer);

    default List<Match> findAll(String text) {
        List<Match> matches = new ArrayList<>();
        forEachMatch(text, (id, start, end) -> matches.add(new Match(id, start, end)));
        return List.copyOf(matches);
    }

    default long countMatches(String text) {
        long[] count = {0L};
        forEachMatch(text, (id, start, end) -> count[0]++);
        return count[0];
    }
}
