package com.feihong.fashionsearch.common;

import java.time.Instant;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Standard response envelope returned by every Java API endpoint.")
public record ApiResponse<T>(
        @Schema(description = "Whether the request completed successfully", example = "true")
        boolean success,
        @Schema(description = "Endpoint-specific payload; null for errors", nullable = true)
        T data,
        @Schema(description = "Human-readable result or error message", example = "OK")
        String message,
        @Schema(description = "UTC response creation time", example = "2026-09-04T12:00:00Z")
        Instant timestamp
) {
    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(true, data, "OK", Instant.now());
    }

    public static <T> ApiResponse<T> error(String message) {
        return new ApiResponse<>(false, null, message, Instant.now());
    }
}
