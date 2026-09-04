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
import com.feihong.fashionsearch.config.OpenApiSchemas;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;

@RestController
@RequestMapping("/api")
@Tag(name = "Search", description = "Semantic fashion search")
public class SearchController {
    private static final Logger log = LoggerFactory.getLogger(SearchController.class);

    private final SearchService searchService;

    public SearchController(SearchService searchService) {
        this.searchService = searchService;
    }

    @PostMapping("/search")
    @Operation(
            summary = "Search fashion items",
            description = "Ranks fashion items by semantic similarity to a natural-language query. "
                    + "The response keeps the standard ApiResponse envelope.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200", description = "Ranked search results",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.SearchApiResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "400", description = "Invalid query or topK value",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.ErrorApiResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "502", description = "AI search service returned an invalid or failed response",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.ErrorApiResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "503", description = "AI search service is unavailable",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.ErrorApiResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "504", description = "AI search service timed out",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.ErrorApiResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "500", description = "Unexpected server error",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.ErrorApiResponse.class)))
    })
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
