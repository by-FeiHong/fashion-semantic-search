package com.feihong.fashionsearch.history;

import java.util.List;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface SearchHistoryRepository extends JpaRepository<SearchHistory, Long> {
    @Query("""
            select count(h) as totalSearches,
                   coalesce(sum(case when h.cacheHit = true then 1 else 0 end), 0) as cacheHits,
                   coalesce(avg(h.durationMs), 0) as averageDurationMs
            from SearchHistory h
            """)
    SearchStatsSummary aggregateStats();

    @Query("""
            select h.query as query, count(h) as count
            from SearchHistory h
            group by h.query
            order by count(h) desc, h.query asc
            """)
    List<TopQueryCount> findTopQueries(Pageable pageable);

    interface SearchStatsSummary {
        long getTotalSearches();

        long getCacheHits();

        double getAverageDurationMs();
    }

    interface TopQueryCount {
        String getQuery();

        long getCount();
    }
}
