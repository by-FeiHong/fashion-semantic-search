package com.feihong.fashionsearch.history;

public interface SearchHistoryPort {
    void save(String query, int topK, long durationMs, boolean cacheHit);
}
