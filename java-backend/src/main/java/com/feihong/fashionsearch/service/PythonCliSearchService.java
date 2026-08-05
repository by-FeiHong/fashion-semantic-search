package com.feihong.fashionsearch.service;

import java.util.List;
import java.util.Locale;
import java.util.Optional;

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
    private final CachePort cache;

    public PythonCliSearchService(SearchEnginePort searchEngine, CachePort cache) {
        this.searchEngine = searchEngine;
        this.cache = cache;
    }

    @Override
    public List<SearchResult> search(SearchRequest request) {
        String query = normalizeQuery(request.query());
        int topK = request.resolvedTopK();
        String queryHash = RedisSearchCacheAdapter.queryHash(query).substring(0, 12);
        long startedAt = System.nanoTime();
        log.info("event=search_service_started queryHash={} topK={}",
                queryHash, topK);
        try {
            Optional<List<SearchResult>> cachedResults = readCache(
                    query, queryHash, topK
            );
            if (cachedResults.isPresent()) {
                List<SearchResult> results = cachedResults.get();
                log.info(
                        "event=search_cache_hit queryHash={} topK={} "
                                + "resultCount={} durationMs={}",
                        queryHash, topK, results.size(), elapsedMillis(startedAt)
                );
                return results;
            }
            log.info("event=search_cache_miss queryHash={} topK={} durationMs={}",
                    queryHash, topK, elapsedMillis(startedAt));
            List<SearchResult> results = searchEngine.search(query, topK);
            writeCache(query, queryHash, topK, results);
            log.info(
                    "event=search_service_succeeded queryHash={} topK={} "
                            + "resultCount={} durationMs={}",
                    queryHash, topK, results.size(), elapsedMillis(startedAt)
            );
            return results;
        } catch (RuntimeException exception) {
            log.warn(
                    "event=search_service_failed queryHash={} topK={} "
                            + "durationMs={} errorType={}",
                    queryHash, topK, elapsedMillis(startedAt),
                    exception.getClass().getSimpleName()
            );
            throw exception;
        }
    }

    private Optional<List<SearchResult>> readCache(
            String query, String queryHash, int topK
    ) {
        long startedAt = System.nanoTime();
        try {
            return cache.get(query, topK);
        } catch (RuntimeException exception) {
            log.warn(
                    "event=search_cache_read_failed queryHash={} topK={} "
                            + "durationMs={} errorType={}",
                    queryHash, topK, elapsedMillis(startedAt),
                    exception.getClass().getSimpleName()
            );
            return Optional.empty();
        }
    }

    private void writeCache(
            String query,
            String queryHash,
            int topK,
            List<SearchResult> results
    ) {
        long startedAt = System.nanoTime();
        try {
            cache.put(query, topK, results);
            log.info(
                    "event=search_cache_write_succeeded queryHash={} topK={} "
                            + "resultCount={} durationMs={}",
                    queryHash, topK, results.size(), elapsedMillis(startedAt)
            );
        } catch (RuntimeException exception) {
            log.warn(
                    "event=search_cache_write_failed queryHash={} topK={} "
                            + "durationMs={} errorType={}",
                    queryHash, topK, elapsedMillis(startedAt),
                    exception.getClass().getSimpleName()
            );
        }
    }

    private String normalizeQuery(String query) {
        return query.trim().replaceAll("\\s+", " ").toLowerCase(Locale.ROOT);
    }

    private long elapsedMillis(long startedAt) {
        return (System.nanoTime() - startedAt) / 1_000_000;
    }
}
