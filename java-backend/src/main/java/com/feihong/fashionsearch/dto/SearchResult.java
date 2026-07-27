package com.feihong.fashionsearch.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record SearchResult(
        @JsonProperty("item_id")
        String itemId,
        double score,
        @JsonProperty("image_path")
        String imagePath,
        String color,
        String description
) {
}
