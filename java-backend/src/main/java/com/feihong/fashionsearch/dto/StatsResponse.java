package com.feihong.fashionsearch.dto;

import java.util.List;

public record StatsResponse(
        long totalSearches,
        double cacheHitRate,
        double averageDurationMs,
        List<TopQuery> topQueries
) {
}
