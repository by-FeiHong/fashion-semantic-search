package com.feihong.fashionsearch.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.feihong.fashionsearch.config.SearchCacheProperties;
import com.feihong.fashionsearch.dto.SearchResult;

@Component
public class RedisSearchCacheAdapter implements CachePort {
    private static final TypeReference<List<SearchResult>> RESULT_LIST =
            new TypeReference<>() {};

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    private final SearchCacheProperties properties;

    public RedisSearchCacheAdapter(
            StringRedisTemplate redisTemplate,
            ObjectMapper objectMapper,
            SearchCacheProperties properties
    ) {
        this.redisTemplate = redisTemplate;
        this.objectMapper = objectMapper;
        this.properties = properties;
    }

    @Override
    public Optional<List<SearchResult>> get(String normalizedQuery, int topK) {
        String value = redisTemplate.opsForValue().get(cacheKey(normalizedQuery, topK));
        if (value == null) {
            return Optional.empty();
        }
        try {
            return Optional.of(objectMapper.readValue(value, RESULT_LIST));
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Cached search result is invalid", exception);
        }
    }

    @Override
    public void put(String normalizedQuery, int topK, List<SearchResult> results) {
        try {
            String value = objectMapper.writeValueAsString(results);
            redisTemplate.opsForValue().set(
                    cacheKey(normalizedQuery, topK),
                    value,
                    properties.ttl()
            );
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Search result cannot be serialized", exception);
        }
    }

    private String cacheKey(String normalizedQuery, int topK) {
        return "%s:q:%s:topk:%d".formatted(
                properties.keyPrefix(),
                queryHash(normalizedQuery),
                topK
        );
    }

    static String queryHash(String normalizedQuery) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(normalizedQuery.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
