package com.feihong.fashionsearch.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Semantic fashion search request")
public record SearchRequest(
        @Schema(description = "Natural-language description of the desired fashion item", example = "minimal black dress")
        @NotBlank(message = "must not be blank") String query,
        @Schema(description = "Maximum number of results; defaults to 5 when omitted", example = "5", minimum = "1", maximum = "20", nullable = true)
        @Min(value = 1, message = "must be at least 1")
        @Max(value = 20, message = "must not exceed 20") Integer topK
) {
    public int resolvedTopK() {
        return topK == null ? 5 : topK;
    }
}
