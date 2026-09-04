package com.feihong.fashionsearch.config;

import java.time.Instant;
import java.util.List;

import com.feihong.fashionsearch.dto.HealthResponse;
import com.feihong.fashionsearch.dto.SearchResult;
import com.feihong.fashionsearch.dto.StatsResponse;
import io.swagger.v3.oas.annotations.media.Schema;

public final class OpenApiSchemas {
    private OpenApiSchemas() {
    }

    @Schema(name = "HealthApiResponse", description = "Successful health response envelope")
    public record HealthApiResponse(
            boolean success, HealthResponse data, String message, Instant timestamp) {
    }

    @Schema(name = "SearchApiResponse", description = "Successful search response envelope")
    public record SearchApiResponse(
            boolean success, List<SearchResult> data, String message, Instant timestamp) {
    }

    @Schema(name = "StatsApiResponse", description = "Successful statistics response envelope")
    public record StatsApiResponse(
            boolean success, StatsResponse data, String message, Instant timestamp) {
    }

    @Schema(name = "ErrorApiResponse", description = "Standard error response envelope")
    public record ErrorApiResponse(
            @Schema(example = "false") boolean success,
            @Schema(nullable = true, example = "null") Object data,
            @Schema(example = "query: must not be blank") String message,
            Instant timestamp) {
    }
}
