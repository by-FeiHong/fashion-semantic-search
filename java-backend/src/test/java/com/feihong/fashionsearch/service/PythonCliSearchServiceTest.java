package com.feihong.fashionsearch.service;

import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.Test;

import com.feihong.fashionsearch.dto.SearchRequest;
import com.feihong.fashionsearch.dto.SearchResult;
import com.feihong.fashionsearch.history.SearchHistoryPort;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PythonCliSearchServiceTest {
    private final SearchEnginePort searchEngine = mock(SearchEnginePort.class);
    private final CachePort cache = mock(CachePort.class);
    private final SearchHistoryPort searchHistory = mock(SearchHistoryPort.class);
    private final PythonCliSearchService service =
            new PythonCliSearchService(searchEngine, cache, searchHistory);
    private final SearchResult result = mock(SearchResult.class);

    @Test
    void cacheHitDoesNotCallSearchEngine() {
        when(cache.get("minimal black dress", 5))
                .thenReturn(Optional.of(List.of(result)));

        List<SearchResult> results = service.search(
                new SearchRequest("  Minimal   Black Dress  ", 5)
        );

        assertThat(results).containsExactly(result);
        verify(searchEngine, never()).search("minimal black dress", 5);
        verify(cache, never()).put(
                "minimal black dress", 5, List.of(result)
        );
    }

    @Test
    void cacheMissCallsSearchEngineAndWritesResult() {
        when(cache.get("minimal black dress", 5)).thenReturn(Optional.empty());
        when(searchEngine.search("minimal black dress", 5))
                .thenReturn(List.of(result));

        List<SearchResult> results = service.search(
                new SearchRequest("minimal black dress", 5)
        );

        assertThat(results).containsExactly(result);
        verify(searchEngine).search("minimal black dress", 5);
        verify(cache).put("minimal black dress", 5, List.of(result));
    }

    @Test
    void cacheReadFailureFallsBackToSearchEngine() {
        when(cache.get("minimal black dress", 5))
                .thenThrow(new IllegalStateException("Redis unavailable"));
        when(searchEngine.search("minimal black dress", 5))
                .thenReturn(List.of(result));

        List<SearchResult> results = service.search(
                new SearchRequest("minimal black dress", 5)
        );

        assertThat(results).containsExactly(result);
        verify(searchEngine).search("minimal black dress", 5);
        verify(cache).put("minimal black dress", 5, List.of(result));
    }

    @Test
    void cacheWriteFailureDoesNotFailSearch() {
        when(cache.get("minimal black dress", 5)).thenReturn(Optional.empty());
        when(searchEngine.search("minimal black dress", 5))
                .thenReturn(List.of(result));
        doThrow(new IllegalStateException("Redis unavailable"))
                .when(cache)
                .put("minimal black dress", 5, List.of(result));

        List<SearchResult> results = service.search(
                new SearchRequest("minimal black dress", 5)
        );

        assertThat(results).containsExactly(result);
        verify(searchEngine).search("minimal black dress", 5);
    }
}
