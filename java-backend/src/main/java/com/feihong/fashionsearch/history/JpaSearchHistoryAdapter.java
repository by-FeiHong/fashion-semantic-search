package com.feihong.fashionsearch.history;

import org.springframework.stereotype.Component;

@Component
public class JpaSearchHistoryAdapter implements SearchHistoryPort {
    private final SearchHistoryRepository repository;

    public JpaSearchHistoryAdapter(SearchHistoryRepository repository) {
        this.repository = repository;
    }

    @Override
    public void save(String query, int topK, long durationMs, boolean cacheHit) {
        repository.save(new SearchHistory(query, topK, durationMs, cacheHit));
    }
}
