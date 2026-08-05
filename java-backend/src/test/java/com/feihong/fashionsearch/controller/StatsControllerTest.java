package com.feihong.fashionsearch.controller;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import com.feihong.fashionsearch.dto.StatsResponse;
import com.feihong.fashionsearch.dto.TopQuery;
import com.feihong.fashionsearch.service.StatsService;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(StatsController.class)
class StatsControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private StatsService statsService;

    @Test
    void usesDefaultLimitAndResponseEnvelope() throws Exception {
        when(statsService.getStats(10)).thenReturn(new StatsResponse(
                2, 0.5, 125.0, List.of(new TopQuery("black dress", 2))
        ));

        mockMvc.perform(get("/api/stats"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.totalSearches").value(2))
                .andExpect(jsonPath("$.data.cacheHitRate").value(0.5))
                .andExpect(jsonPath("$.data.averageDurationMs").value(125.0))
                .andExpect(jsonPath("$.data.topQueries[0].query").value("black dress"))
                .andExpect(jsonPath("$.data.topQueries[0].count").value(2));

        verify(statsService).getStats(10);
    }

    @Test
    void passesCustomLimitToService() throws Exception {
        when(statsService.getStats(3))
                .thenReturn(new StatsResponse(0, 0, 0, List.of()));

        mockMvc.perform(get("/api/stats").param("limit", "3"))
                .andExpect(status().isOk());

        verify(statsService).getStats(3);
    }

    @Test
    void rejectsLimitOutsideAllowedRange() throws Exception {
        mockMvc.perform(get("/api/stats").param("limit", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("limit: must be at least 1"));

        mockMvc.perform(get("/api/stats").param("limit", "51"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("limit: must not exceed 50"));
    }
}
