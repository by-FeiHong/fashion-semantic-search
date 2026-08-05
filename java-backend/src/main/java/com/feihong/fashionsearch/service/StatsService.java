package com.feihong.fashionsearch.service;

import java.util.List;

import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.feihong.fashionsearch.dto.StatsResponse;
import com.feihong.fashionsearch.dto.TopQuery;
import com.feihong.fashionsearch.history.SearchHistoryRepository;

@Service
public class StatsService {
    private final SearchHistoryRepository repository;

    public StatsService(SearchHistoryRepository repository) {
        this.repository = repository;
    }

    @Transactional(readOnly = true)
    public StatsResponse getStats(int limit) {
        SearchHistoryRepository.SearchStatsSummary summary = repository.aggregateStats();
        long totalSearches = summary.getTotalSearches();
        double cacheHitRate = totalSearches == 0
                ? 0.0
                : (double) summary.getCacheHits() / totalSearches;
        List<TopQuery> topQueries = repository.findTopQueries(PageRequest.of(0, limit))
                .stream()
                .map(row -> new TopQuery(row.getQuery(), row.getCount()))
                .toList();

        return new StatsResponse(
                totalSearches,
                cacheHitRate,
                totalSearches == 0 ? 0.0 : summary.getAverageDurationMs(),
                topQueries
        );
    }
}
