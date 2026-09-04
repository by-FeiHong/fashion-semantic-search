package com.feihong.fashionsearch.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Java backend health status")
public record HealthResponse(
        @Schema(description = "Service readiness status", example = "UP") String status,
        @Schema(description = "Service identifier", example = "fashion-search-backend") String service
) {
}
