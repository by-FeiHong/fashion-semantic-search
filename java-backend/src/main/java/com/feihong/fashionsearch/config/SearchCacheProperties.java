package com.feihong.fashionsearch.config;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "fashion-search.cache")
public record SearchCacheProperties(String keyPrefix, Duration ttl) {
    public SearchCacheProperties {
        if (keyPrefix == null || keyPrefix.isBlank()) {
            throw new IllegalArgumentException("Cache key prefix must not be blank");
        }
        if (ttl == null || ttl.isZero() || ttl.isNegative()) {
            throw new IllegalArgumentException("Cache TTL must be positive");
        }
    }
}
