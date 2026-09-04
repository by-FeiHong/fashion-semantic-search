package com.feihong.fashionsearch.dto;

import java.util.List;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Aggregated search-history statistics")
public record StatsResponse(
        @Schema(description = "Total recorded searches", example = "120") long totalSearches,
        @Schema(description = "Fraction of searches served from cache", example = "0.75") double cacheHitRate,
        @Schema(description = "Mean search duration in milliseconds", example = "214.5") double averageDurationMs,
        @Schema(description = "Most frequent normalized queries") List<TopQuery> topQueries
) {
}
