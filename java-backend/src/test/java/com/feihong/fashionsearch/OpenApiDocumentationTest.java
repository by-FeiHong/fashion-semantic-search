package com.feihong.fashionsearch;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import com.feihong.fashionsearch.service.SearchService;
import com.feihong.fashionsearch.service.StatsService;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class OpenApiDocumentationTest {
    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private SearchService searchService;

    @MockBean
    private StatsService statsService;

    @Test
    void exposesDocumentedSearchAndStatsEndpoints() throws Exception {
        mockMvc.perform(get("/v3/api-docs"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.openapi").isString())
                .andExpect(jsonPath("$.paths['/api/search'].post").exists())
                .andExpect(jsonPath("$.paths['/api/stats'].get").exists())
                .andExpect(jsonPath("$.paths['/api/search'].post.requestBody.content['application/json'].schema['$ref']")
                        .value("#/components/schemas/SearchRequest"))
                .andExpect(jsonPath("$.paths['/api/search'].post.responses['200'].content['*/*'].schema['$ref']")
                        .value("#/components/schemas/SearchApiResponse"))
                .andExpect(jsonPath("$.paths['/api/stats'].get.responses['200'].content['*/*'].schema['$ref']")
                        .value("#/components/schemas/StatsApiResponse"));
    }

    @Test
    void exposesSwaggerUi() throws Exception {
        mockMvc.perform(get("/swagger-ui.html"))
                .andExpect(status().is3xxRedirection());
    }
}
