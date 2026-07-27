package com.feihong.fashionsearch.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

public record SearchRequest(
        @NotBlank(message = "must not be blank") String query,
        @Min(value = 1, message = "must be at least 1")
        @Max(value = 20, message = "must not exceed 20") Integer topK
) {
    public int resolvedTopK() {
        return topK == null ? 5 : topK;
    }
}
