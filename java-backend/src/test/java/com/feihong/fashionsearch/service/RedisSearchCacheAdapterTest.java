package com.feihong.fashionsearch.service;

import java.time.Duration;

import org.junit.jupiter.api.Test;

import com.feihong.fashionsearch.config.SearchCacheProperties;

import static org.assertj.core.api.Assertions.assertThat;

class RedisSearchCacheAdapterTest {
    @Test
    void queryHashIsStableAndDoesNotExposeQuery() {
        String hash = RedisSearchCacheAdapter.queryHash("minimal black dress");

        assertThat(hash)
                .hasSize(64)
                .doesNotContain("minimal", "black", "dress")
                .isEqualTo(RedisSearchCacheAdapter.queryHash(
                        "minimal black dress"
                ));
    }

    @Test
    void cachePropertiesAcceptPositiveTtl() {
        SearchCacheProperties properties = new SearchCacheProperties(
                "fashion-search:search:v1",
                Duration.ofMinutes(10)
        );

        assertThat(properties.ttl()).isEqualTo(Duration.ofMinutes(10));
    }
}
