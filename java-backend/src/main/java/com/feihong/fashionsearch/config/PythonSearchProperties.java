package com.feihong.fashionsearch.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fashion-search.python")
public record PythonSearchProperties(
        String executable,
        String projectRoot,
        String searchScript,
        Duration timeout
) {
}
