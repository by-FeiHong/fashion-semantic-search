package com.feihong.fashionsearch.service;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.data.domain.Pageable;

import com.feihong.fashionsearch.history.SearchHistoryRepository;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

class StatsServiceTest {
    private final SearchHistoryRepository repository =
            Mockito.mock(SearchHistoryRepository.class);
    private final StatsService service = new StatsService(repository);

    @Test
    void returnsZerosForEmptyHistory() {
        SearchHistoryRepository.SearchStatsSummary emptySummary = summary(0, 0, 0);
        when(repository.aggregateStats()).thenReturn(emptySummary);
        when(repository.findTopQueries(any(Pageable.class))).thenReturn(List.of());

        var stats = service.getStats(10);

        assertThat(stats.totalSearches()).isZero();
        assertThat(stats.cacheHitRate()).isZero();
        assertThat(stats.averageDurationMs()).isZero();
        assertThat(stats.topQueries()).isEmpty();
    }

    private SearchHistoryRepository.SearchStatsSummary summary(
            long total, long cacheHits, double average
    ) {
        SearchHistoryRepository.SearchStatsSummary summary =
                Mockito.mock(SearchHistoryRepository.SearchStatsSummary.class);
        when(summary.getTotalSearches()).thenReturn(total);
        when(summary.getCacheHits()).thenReturn(cacheHits);
        when(summary.getAverageDurationMs()).thenReturn(average);
        return summary;
    }
}
