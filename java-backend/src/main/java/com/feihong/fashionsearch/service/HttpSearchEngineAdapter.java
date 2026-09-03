package com.feihong.fashionsearch.service;

import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.util.Arrays;
import java.util.List;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import com.feihong.fashionsearch.config.AiServiceProperties;
import com.feihong.fashionsearch.dto.SearchResult;
import com.feihong.fashionsearch.exception.AiServiceInvalidResponseException;
import com.feihong.fashionsearch.exception.AiServiceTimeoutException;
import com.feihong.fashionsearch.exception.AiServiceUnavailableException;
import com.feihong.fashionsearch.exception.AiServiceUpstreamException;

@Component
public class HttpSearchEngineAdapter implements SearchEnginePort {
    private static final Logger log = LoggerFactory.getLogger(HttpSearchEngineAdapter.class);

    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public HttpSearchEngineAdapter(AiServiceProperties properties, ObjectMapper objectMapper) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(properties.connectTimeout());
        requestFactory.setReadTimeout(properties.readTimeout());
        this.restClient = RestClient.builder()
                .baseUrl(properties.baseUrl())
                .requestFactory(requestFactory)
                .build();
        this.objectMapper = objectMapper;
    }

    @Override
    public List<SearchResult> search(String query, int topK) {
        long startedAt = System.nanoTime();
        try {
            String body = restClient.post()
                    .uri("/search")
                    .body(new AiSearchRequest(query, topK))
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (request, response) -> {
                        throw new AiServiceUpstreamException(
                                "The AI search service returned HTTP " + response.getStatusCode().value() + "."
                        );
                    })
                    .body(String.class);
            if (body == null) {
                throw new AiServiceInvalidResponseException("The AI search service returned an empty response.");
            }
            List<SearchResult> results = Arrays.asList(
                    objectMapper.readValue(body, SearchResult[].class)
            );
            log.info("event=ai_search_succeeded topK={} resultCount={} durationMs={}",
                    topK, results.size(), elapsedMillis(startedAt));
            return results;
        } catch (JsonProcessingException exception) {
            throw new AiServiceInvalidResponseException(
                    "The AI search service returned an invalid response.", exception
            );
        } catch (AiServiceUpstreamException | AiServiceInvalidResponseException exception) {
            throw exception;
        } catch (ResourceAccessException exception) {
            if (hasCause(exception, SocketTimeoutException.class)) {
                throw new AiServiceTimeoutException("The AI search service timed out.", exception);
            }
            if (hasCause(exception, ConnectException.class)) {
                throw new AiServiceUnavailableException("The AI search service is unavailable.", exception);
            }
            throw new AiServiceUnavailableException("The AI search service could not be reached.", exception);
        } catch (RestClientResponseException exception) {
            throw new AiServiceUpstreamException(
                    "The AI search service returned HTTP " + exception.getStatusCode().value() + ".",
                    exception
            );
        } catch (RestClientException exception) {
            if (hasCause(exception, SocketTimeoutException.class)) {
                throw new AiServiceTimeoutException("The AI search service timed out.", exception);
            }
            throw new AiServiceInvalidResponseException(
                    "The AI search service returned an unreadable response.", exception
            );
        }
    }

    private boolean hasCause(Throwable throwable, Class<? extends Throwable> type) {
        for (Throwable cause = throwable; cause != null; cause = cause.getCause()) {
            if (type.isInstance(cause)) return true;
        }
        return false;
    }

    private long elapsedMillis(long startedAt) {
        return (System.nanoTime() - startedAt) / 1_000_000;
    }

    private record AiSearchRequest(String query, int topK) { }
}
