package com.feihong.fashionsearch.service;

import java.util.List;

import com.feihong.fashionsearch.dto.SearchResult;

/**
 * Technology-neutral port for semantic search engines.
 */
public interface SearchEnginePort {
    List<SearchResult> search(String query, int topK);
}
