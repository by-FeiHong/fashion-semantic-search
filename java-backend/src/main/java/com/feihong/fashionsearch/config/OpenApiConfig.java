package com.feihong.fashionsearch.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {
    @Bean
    public OpenAPI fashionSearchOpenApi() {
        return new OpenAPI().info(new Info()
                .title("Fashion Semantic Search API")
                .description("Spring Boot API for health checks, semantic fashion search, and search statistics.")
                .version("v1"));
    }
}
