package com.feihong.fashionsearch.service;

import java.io.IOException;
import java.time.Duration;

import com.fasterxml.jackson.databind.ObjectMapper;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.feihong.fashionsearch.config.AiServiceProperties;
import com.feihong.fashionsearch.exception.AiServiceInvalidResponseException;
import com.feihong.fashionsearch.exception.AiServiceTimeoutException;
import com.feihong.fashionsearch.exception.AiServiceUpstreamException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class HttpSearchEngineAdapterTest {
    private MockWebServer server;

    @BeforeEach
    void startServer() throws IOException { server = new MockWebServer(); server.start(); }

    @AfterEach
    void stopServer() throws IOException { server.shutdown(); }

    @Test
    void returnsCompatibleSearchResults() throws InterruptedException {
        server.enqueue(new MockResponse().setHeader("Content-Type", "application/json")
                .setBody("[{\"item_id\":\"42\",\"score\":0.91,\"image_path\":\"image.jpg\",\"color\":\"black\",\"description\":\"dress\"}]"));

        var results = adapter(Duration.ofSeconds(1)).search("black dress", 3);

        assertThat(results).hasSize(1);
        assertThat(results.get(0).itemId()).isEqualTo("42");
        var request = server.takeRequest();
        assertThat(request.getPath()).isEqualTo("/search");
        assertThat(request.getBody().readUtf8()).contains("\"query\":\"black dress\"", "\"topK\":3");
    }

    @Test
    void mapsTimeout() {
        server.enqueue(new MockResponse().setBody("[]").setBodyDelay(500, java.util.concurrent.TimeUnit.MILLISECONDS));
        assertThatThrownBy(() -> adapter(Duration.ofMillis(50)).search("dress", 3))
                .isInstanceOf(AiServiceTimeoutException.class);
    }

    @Test
    void mapsServerError() {
        server.enqueue(new MockResponse().setResponseCode(503));
        assertThatThrownBy(() -> adapter(Duration.ofSeconds(1)).search("dress", 3))
                .isInstanceOf(AiServiceUpstreamException.class);
    }

    @Test
    void mapsInvalidJson() {
        server.enqueue(new MockResponse().setBody("not-json"));
        assertThatThrownBy(() -> adapter(Duration.ofSeconds(1)).search("dress", 3))
                .isInstanceOf(AiServiceInvalidResponseException.class);
    }

    private HttpSearchEngineAdapter adapter(Duration readTimeout) {
        return new HttpSearchEngineAdapter(
                new AiServiceProperties(server.url("/").toString(), Duration.ofSeconds(1), readTimeout),
                new ObjectMapper()
        );
    }
}
