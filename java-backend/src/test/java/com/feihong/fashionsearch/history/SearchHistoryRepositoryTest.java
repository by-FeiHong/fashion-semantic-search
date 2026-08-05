package com.feihong.fashionsearch.history;

import java.util.Arrays;

import org.junit.jupiter.api.Test;
import org.springframework.data.domain.PageRequest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.test.context.ActiveProfiles;

import jakarta.persistence.Table;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@ActiveProfiles("test")
class SearchHistoryRepositoryTest {
    @Autowired
    private SearchHistoryRepository repository;

    @Test
    void savesAndLoadsSearchHistoryWithGeneratedFields() {
        SearchHistory history = new SearchHistory("minimal black dress", 5, 42L, true);

        SearchHistory saved = repository.saveAndFlush(history);
        SearchHistory loaded = repository.findById(saved.getId()).orElseThrow();

        assertThat(loaded.getId()).isPositive();
        assertThat(loaded.getQuery()).isEqualTo("minimal black dress");
        assertThat(loaded.getTopK()).isEqualTo(5);
        assertThat(loaded.getDurationMs()).isEqualTo(42L);
        assertThat(loaded.isCacheHit()).isTrue();
        assertThat(loaded.getCreatedAt()).isNotNull();
    }

    @Test
    void mapsToExplicitTableWithExpectedIndexes() {
        Table table = SearchHistory.class.getAnnotation(Table.class);

        assertThat(table.name()).isEqualTo("search_history");
        assertThat(Arrays.stream(table.indexes()).map(index -> index.name()))
                .containsExactlyInAnyOrder(
                        "idx_search_history_query",
                        "idx_search_history_created_at"
                );
    }

    @Test
    void aggregatesStatsAndReturnsStableTopQueries() {
        repository.saveAllAndFlush(Arrays.asList(
                new SearchHistory("zebra coat", 5, 100L, true),
                new SearchHistory("amber dress", 5, 200L, false),
                new SearchHistory("zebra coat", 10, 300L, true),
                new SearchHistory("amber dress", 3, 400L, false),
                new SearchHistory("blue jeans", 5, 500L, false)
        ));

        SearchHistoryRepository.SearchStatsSummary summary = repository.aggregateStats();
        var topQueries = repository.findTopQueries(PageRequest.of(0, 2));

        assertThat(summary.getTotalSearches()).isEqualTo(5);
        assertThat(summary.getCacheHits()).isEqualTo(2);
        assertThat(summary.getAverageDurationMs()).isEqualTo(300.0);
        assertThat(topQueries).extracting(
                        SearchHistoryRepository.TopQueryCount::getQuery,
                        SearchHistoryRepository.TopQueryCount::getCount
                )
                .containsExactly(
                        org.assertj.core.groups.Tuple.tuple("amber dress", 2L),
                        org.assertj.core.groups.Tuple.tuple("zebra coat", 2L)
                );
    }

    @Test
    void aggregatesEmptyHistoryAsZeros() {
        SearchHistoryRepository.SearchStatsSummary summary = repository.aggregateStats();

        assertThat(summary.getTotalSearches()).isZero();
        assertThat(summary.getCacheHits()).isZero();
        assertThat(summary.getAverageDurationMs()).isZero();
        assertThat(repository.findTopQueries(PageRequest.of(0, 10))).isEmpty();
    }
}
