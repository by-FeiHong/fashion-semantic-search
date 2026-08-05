package com.feihong.fashionsearch.history;

import java.util.Arrays;

import org.junit.jupiter.api.Test;
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
}
