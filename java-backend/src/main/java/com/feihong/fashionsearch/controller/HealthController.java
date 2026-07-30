package com.feihong.fashionsearch.controller;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.feihong.fashionsearch.common.ApiResponse;
import com.feihong.fashionsearch.dto.HealthResponse;

@RestController
@RequestMapping("/api")
public class HealthController {
    private static final Logger log = LoggerFactory.getLogger(HealthController.class);

    @GetMapping("/health")
    public ApiResponse<HealthResponse> health() {
        long startedAt = System.nanoTime();
        log.info("event=health_request_received");
        ApiResponse<HealthResponse> response =
                ApiResponse.success(new HealthResponse("UP", "fashion-search-backend"));
        log.info("event=health_request_succeeded durationMs={}",
                (System.nanoTime() - startedAt) / 1_000_000);
        return response;
    }
}
