package com.feihong.fashionsearch.service;

import java.util.List;
import java.util.Optional;

import com.feihong.fashionsearch.dto.SearchResult;

/**
 * Technology-neutral cache boundary for semantic search results.
 */
public interface CachePort {
    Optional<List<SearchResult>> get(String normalizedQuery, int topK);

    void put(String normalizedQuery, int topK, List<SearchResult> results);
}
