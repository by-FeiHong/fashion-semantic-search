package com.feihong.fashionsearch.service;

import java.util.List;

import org.junit.jupiter.api.Test;

import com.feihong.fashionsearch.dto.SearchRequest;
import com.feihong.fashionsearch.dto.SearchResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PythonCliSearchServiceTest {
    @Test
    void delegatesThroughSearchEnginePort() {
        SearchEnginePort port = mock(SearchEnginePort.class);
        SearchResult result = mock(SearchResult.class);
        when(port.search("minimal black dress", 5))
                .thenReturn(List.of(result));
        PythonCliSearchService service = new PythonCliSearchService(port);

        List<SearchResult> results = service.search(
                new SearchRequest("  minimal black dress  ", 5)
        );

        assertThat(results).containsExactly(result);
        verify(port).search("minimal black dress", 5);
    }
}
