package com.feihong.fashionsearch.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "A frequently submitted search query")
public record TopQuery(
        @Schema(description = "Normalized query text", example = "minimal black dress") String query,
        @Schema(description = "Number of occurrences", example = "24") long count
) {
}
