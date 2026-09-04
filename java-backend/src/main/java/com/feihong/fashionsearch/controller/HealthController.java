package com.feihong.fashionsearch.controller;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.feihong.fashionsearch.common.ApiResponse;
import com.feihong.fashionsearch.dto.HealthResponse;
import com.feihong.fashionsearch.config.OpenApiSchemas;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;

@RestController
@RequestMapping("/api")
@Tag(name = "Health", description = "Java backend readiness")
public class HealthController {
    private static final Logger log = LoggerFactory.getLogger(HealthController.class);

    @GetMapping("/health")
    @Operation(summary = "Check backend health", description = "Returns the readiness status of the Spring Boot API.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200", description = "Backend is available",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.HealthApiResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "500", description = "Unexpected server error",
                    content = @Content(schema = @Schema(implementation = OpenApiSchemas.ErrorApiResponse.class)))
    })
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
