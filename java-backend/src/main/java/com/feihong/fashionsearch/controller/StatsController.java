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

@Validated
@RestController
@RequestMapping("/api")
public class StatsController {
    private final StatsService statsService;

    public StatsController(StatsService statsService) {
        this.statsService = statsService;
    }

    @GetMapping("/stats")
    public ApiResponse<StatsResponse> stats(
            @RequestParam(defaultValue = "10")
            @Min(value = 1, message = "must be at least 1")
            @Max(value = 50, message = "must not exceed 50") int limit
    ) {
        return ApiResponse.success(statsService.getStats(limit));
    }
}
