package com.feihong.fashionsearch.common;

import java.time.Instant;

public record ApiResponse<T>(
        boolean success, T data, String message, Instant timestamp
) {
    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(true, data, "OK", Instant.now());
    }

    public static <T> ApiResponse<T> error(String message) {
        return new ApiResponse<>(false, null, message, Instant.now());
    }
}
