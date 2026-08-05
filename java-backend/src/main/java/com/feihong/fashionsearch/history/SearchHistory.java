package com.feihong.fashionsearch.history;

import java.time.Instant;

import org.hibernate.annotations.CreationTimestamp;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

@Entity
@Table(
        name = "search_history",
        indexes = {
                @Index(name = "idx_search_history_query", columnList = "search_query"),
                @Index(name = "idx_search_history_created_at", columnList = "created_at")
        }
)
public class SearchHistory {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "search_query", nullable = false, length = 255)
    private String query;

    @Column(name = "top_k", nullable = false)
    private int topK;

    @Column(name = "duration_ms", nullable = false)
    private long durationMs;

    @Column(name = "cache_hit", nullable = false)
    private boolean cacheHit;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    protected SearchHistory() {
    }

    public SearchHistory(String query, int topK, long durationMs, boolean cacheHit) {
        this.query = query;
        this.topK = topK;
        this.durationMs = durationMs;
        this.cacheHit = cacheHit;
    }

    public Long getId() {
        return id;
    }

    public String getQuery() {
        return query;
    }

    public int getTopK() {
        return topK;
    }

    public long getDurationMs() {
        return durationMs;
    }

    public boolean isCacheHit() {
        return cacheHit;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
