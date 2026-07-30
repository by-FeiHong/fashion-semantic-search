package com.feihong.fashionsearch.controller;

import java.util.List;

import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.feihong.fashionsearch.common.ApiResponse;
import com.feihong.fashionsearch.dto.SearchRequest;
import com.feihong.fashionsearch.dto.SearchResult;
import com.feihong.fashionsearch.service.SearchService;

@RestController
@RequestMapping("/api")
public class SearchController {
    private static final Logger log = LoggerFactory.getLogger(SearchController.class);

    private final SearchService searchService;

    public SearchController(SearchService searchService) {
        this.searchService = searchService;
    }

    @PostMapping("/search")
    public ApiResponse<List<SearchResult>> search(
            @Valid @RequestBody SearchRequest request
    ) {
        long startedAt = System.nanoTime();
        int topK = request.resolvedTopK();
        log.info("event=search_request_received query=\"{}\" topK={}",
                request.query(), topK);
        try {
            ApiResponse<List<SearchResult>> response =
                    ApiResponse.success(searchService.search(request));
            log.info(
                    "event=search_request_succeeded query=\"{}\" topK={} "
                            + "durationMs={}",
                    request.query(), topK, elapsedMillis(startedAt)
            );
            return response;
        } catch (RuntimeException exception) {
            log.warn(
                    "event=search_request_failed query=\"{}\" topK={} "
                            + "durationMs={} errorType={}",
                    request.query(), topK, elapsedMillis(startedAt),
                    exception.getClass().getSimpleName()
            );
            throw exception;
        }
    }

    private long elapsedMillis(long startedAt) {
        return (System.nanoTime() - startedAt) / 1_000_000;
    }
}
