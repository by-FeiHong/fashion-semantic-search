package com.feihong.fashionsearch.dto;

public record SearchResult(
        String itemId,
        double score,
        String imagePath,
        String color,
        String description
) {
}
