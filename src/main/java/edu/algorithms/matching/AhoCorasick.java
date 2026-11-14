package edu.algorithms.matching;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Queue;

public final class AhoCorasick implements MultiPatternMatcher {
    private static final int MISSING = -1;

    private final List<String> patterns;
    private final Map<Character, Integer> alphabet;
    private final Node[] states;

    public AhoCorasick(List<String> patterns) {
        this.patterns = PatternInputs.validatedCopy(patterns);
        this.alphabet = buildAlphabet(this.patterns);
        List<Node> trie = buildTrie();
        buildFailureAndOutputLinks(trie);
        this.states = trie.toArray(Node[]::new);
    }

    @Override
    public List<String> patterns() {
        return patterns;
    }

    public int stateCount() {
        return states.length;
    }

    public int alphabetSize() {
        return alphabet.size();
    }

    public long transitionSlotCount() {
        return (long) stateCount() * alphabetSize();
    }

    @Override
    public void forEachMatch(String text, MatchConsumer consumer) {
        Objects.requireNonNull(text, "text");
        Objects.requireNonNull(consumer, "consumer");
        int state = 0;
        for (int index = 0; index < text.length(); index++) {
            Integer symbol = alphabet.get(text.charAt(index));
            if (symbol == null) {
                state = 0;
                continue;
            }
            state = states[state].next[symbol];
            emitMatches(state, index + 1, consumer);
        }
    }

    private void emitMatches(int state, int endExclusive, MatchConsumer consumer) {
        for (int output = state; output != MISSING; output = states[output].output) {
            for (int patternId : states[output].terminalPatternIds) {
                int start = endExclusive - patterns.get(patternId).length();
                consumer.accept(patternId, start, endExclusive);
            }
        }
    }

    private static Map<Character, Integer> buildAlphabet(List<String> patterns) {
        Map<Character, Integer> symbols = new HashMap<>();
        for (String pattern : patterns) {
            for (int index = 0; index < pattern.length(); index++) {
                char symbol = pattern.charAt(index);
                if (!symbols.containsKey(symbol)) {
                    symbols.put(symbol, symbols.size());
                }
            }
        }
        return Map.copyOf(symbols);
    }

    private List<Node> buildTrie() {
        List<Node> trie = new ArrayList<>();
        trie.add(new Node(alphabet.size()));
        for (int patternId = 0; patternId < patterns.size(); patternId++) {
            int state = 0;
            String pattern = patterns.get(patternId);
            for (int index = 0; index < pattern.length(); index++) {
                int symbol = alphabet.get(pattern.charAt(index));
                Node parent = trie.get(state);
                if (parent.next[symbol] == MISSING) {
                    parent.next[symbol] = trie.size();
                    trie.add(new Node(alphabet.size()));
                }
                state = parent.next[symbol];
            }
            trie.get(state).terminalPatternIds.add(patternId);
        }
        return trie;
    }

    private void buildFailureAndOutputLinks(List<Node> trie) {
        Queue<Integer> pending = new ArrayDeque<>();
        Node root = trie.get(0);
        for (int symbol = 0; symbol < alphabet.size(); symbol++) {
            if (root.next[symbol] == MISSING) {
                root.next[symbol] = 0;
            } else {
                pending.add(root.next[symbol]);
            }
        }
        while (!pending.isEmpty()) {
            int state = pending.remove();
            Node parent = trie.get(state);
            Node fallback = trie.get(parent.failure);
            for (int symbol = 0; symbol < alphabet.size(); symbol++) {
                int childId = parent.next[symbol];
                if (childId == MISSING) {
                    parent.next[symbol] = fallback.next[symbol];
                    continue;
                }
                Node child = trie.get(childId);
                child.failure = fallback.next[symbol];
                Node suffix = trie.get(child.failure);
                child.output = suffix.terminalPatternIds.isEmpty()
                        ? suffix.output : child.failure;
                pending.add(childId);
            }
        }
    }

    private static final class Node {
        private final int[] next;
        private final List<Integer> terminalPatternIds = new ArrayList<>();
        private int failure;
        private int output = MISSING;

        private Node(int alphabetSize) {
            next = new int[alphabetSize];
            Arrays.fill(next, MISSING);
        }
    }
}
