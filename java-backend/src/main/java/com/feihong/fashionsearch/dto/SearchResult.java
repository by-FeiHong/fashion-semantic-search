package com.feihong.fashionsearch.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import io.swagger.v3.oas.annotations.media.Schema;

@JsonIgnoreProperties(ignoreUnknown = true)
@Schema(description = "One ranked semantic-search result")
public record SearchResult(
        @JsonProperty("item_id")
        @Schema(description = "Dataset item identifier", example = "id_00000001")
        String itemId,
        @Schema(description = "Cosine similarity score", example = "0.873")
        double score,
        @JsonProperty("image_path")
        @Schema(description = "Path of the representative product image", example = "img/WOMEN/Dresses/id_00000001/01_1_front.jpg")
        String imagePath,
        @Schema(description = "Product color", example = "Black")
        String color,
        @Schema(description = "Product description", example = "Sleeveless solid-color dress")
        String description
) {
}
