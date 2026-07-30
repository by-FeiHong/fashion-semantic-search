package com.feihong.fashionsearch.service;

import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.feihong.fashionsearch.dto.SearchRequest;
import com.feihong.fashionsearch.dto.SearchResult;

@Service
public class PythonCliSearchService implements SearchService {
    private static final Logger log =
            LoggerFactory.getLogger(PythonCliSearchService.class);

    private final SearchEnginePort searchEngine;

    public PythonCliSearchService(SearchEnginePort searchEngine) {
        this.searchEngine = searchEngine;
    }

    @Override
    public List<SearchResult> search(SearchRequest request) {
        String query = request.query().trim();
        int topK = request.resolvedTopK();
        long startedAt = System.nanoTime();
        log.info("event=search_service_started query=\"{}\" topK={}",
                query, topK);
        try {
            List<SearchResult> results = searchEngine.search(query, topK);
            log.info(
                    "event=search_service_succeeded query=\"{}\" topK={} "
                            + "resultCount={} durationMs={}",
                    query, topK, results.size(), elapsedMillis(startedAt)
            );
            return results;
        } catch (RuntimeException exception) {
            log.warn(
                    "event=search_service_failed query=\"{}\" topK={} "
                            + "durationMs={} errorType={}",
                    query, topK, elapsedMillis(startedAt),
                    exception.getClass().getSimpleName()
            );
            throw exception;
        }
    }

    private long elapsedMillis(long startedAt) {
        return (System.nanoTime() - startedAt) / 1_000_000;
    }
}
