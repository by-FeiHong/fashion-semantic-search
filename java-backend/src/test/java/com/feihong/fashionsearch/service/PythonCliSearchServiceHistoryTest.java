package com.feihong.fashionsearch.service;

import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import com.feihong.fashionsearch.dto.SearchRequest;
import com.feihong.fashionsearch.dto.SearchResult;
import com.feihong.fashionsearch.history.SearchHistoryPort;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PythonCliSearchServiceHistoryTest {
    @Mock
    private SearchEnginePort searchEngine;
    @Mock
    private CachePort cache;
    @Mock
    private SearchHistoryPort searchHistory;

    private PythonCliSearchService service;
    private List<SearchResult> results;

    @BeforeEach
    void setUp() {
        service = new PythonCliSearchService(searchEngine, cache, searchHistory);
        results = List.of(new SearchResult(
                "dress-1", 0.91, "images/dress-1.jpg", "black", "Black dress"
        ));
    }

    @Test
    void savesCacheHitHistoryWithTrue() {
        when(cache.get("black dress", 5)).thenReturn(Optional.of(results));

        assertEquals(results, service.search(new SearchRequest(" Black  Dress ", 5)));

        verify(searchHistory).save(org.mockito.ArgumentMatchers.eq("black dress"),
                org.mockito.ArgumentMatchers.eq(5), anyLong(),
                org.mockito.ArgumentMatchers.eq(true));
        verify(searchEngine, never()).search("black dress", 5);
    }

    @Test
    void savesCacheMissHistoryWithFalse() {
        when(cache.get("black dress", 5)).thenReturn(Optional.empty());
        when(searchEngine.search("black dress", 5)).thenReturn(results);

        assertEquals(results, service.search(new SearchRequest("black dress", 5)));

        verify(searchHistory).save(org.mockito.ArgumentMatchers.eq("black dress"),
                org.mockito.ArgumentMatchers.eq(5), anyLong(),
                org.mockito.ArgumentMatchers.eq(false));
    }

    @Test
    void historyFailureDoesNotFailSuccessfulSearch() {
        when(cache.get("black dress", 5)).thenReturn(Optional.of(results));
        doThrow(new IllegalStateException("database unavailable"))
                .when(searchHistory).save(org.mockito.ArgumentMatchers.eq("black dress"),
                        org.mockito.ArgumentMatchers.eq(5), anyLong(),
                        org.mockito.ArgumentMatchers.eq(true));

        assertEquals(results, service.search(new SearchRequest("black dress", 5)));
    }
}
