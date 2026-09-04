package com.feihong.fashionsearch.controller;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.feihong.fashionsearch.common.ApiResponse;
import com.feihong.fashionsearch.dto.StatsResponse;
import com.feihong.fashionsearch.service.StatsService;
import com.feihong.fashionsearch.config.OpenApiSchemas;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;

@Validated
@RestController
@RequestMapping("/api")
@Tag(name = "Statistics", description = "Aggregated search-history metrics")
public class StatsController {
    private final StatsService statsService;

    public StatsController(StatsService statsService) {
        this.statsService = statsService;
    }

    @GetMapping("/stats")
    @Operation(
            summary = "Get search statistics",
            description = "Returns aggregate search count, cache performance, latency, and top queries.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200", description = "Aggregated search statistics",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.StatsApiResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "400", description = "limit is outside the allowed range",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.ErrorApiResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "500", description = "Unexpected server error",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.ErrorApiResponse.class)))
    })
    public ApiResponse<StatsResponse> stats(
            @RequestParam(defaultValue = "10")
            @Parameter(description = "Maximum number of top queries to return", example = "10")
            @Min(value = 1, message = "must be at least 1")
            @Max(value = 50, message = "must not exceed 50") int limit
    ) {
        return ApiResponse.success(statsService.getStats(limit));
    }
}
