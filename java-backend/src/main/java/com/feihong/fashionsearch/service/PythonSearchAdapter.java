package com.feihong.fashionsearch.service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.TimeUnit;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import com.feihong.fashionsearch.config.PythonSearchProperties;
import com.feihong.fashionsearch.dto.SearchResult;
import com.feihong.fashionsearch.exception.PythonJsonParseException;
import com.feihong.fashionsearch.exception.PythonNonZeroExitException;
import com.feihong.fashionsearch.exception.PythonProcessStartException;
import com.feihong.fashionsearch.exception.PythonSearchInterruptedException;
import com.feihong.fashionsearch.exception.PythonSearchTimeoutException;

@Component
public class PythonSearchAdapter implements SearchEnginePort {
    private static final Logger log =
            LoggerFactory.getLogger(PythonSearchAdapter.class);

    private final PythonSearchProperties properties;
    private final ObjectMapper objectMapper;

    public PythonSearchAdapter(
            PythonSearchProperties properties,
            ObjectMapper objectMapper
    ) {
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    @Override
    public List<SearchResult> search(String query, int topK) {
        Path root = Path.of(properties.projectRoot()).toAbsolutePath().normalize();
        Path script = root.resolve(properties.searchScript()).normalize();
        ProcessBuilder builder = new ProcessBuilder(
                properties.executable(),
                script.toString(),
                query,
                "--top-k",
                String.valueOf(topK),
                "--json"
        );
        builder.directory(root.toFile());
        long startedAt = System.nanoTime();
        log.info("event=python_search_started query=\"{}\" topK={}",
                query, topK);

        try {
            Process process = builder.start();
            CompletableFuture<String> stdoutFuture = readStream(process.getInputStream());
            CompletableFuture<String> stderrFuture = readStream(process.getErrorStream());
            if (!process.waitFor(properties.timeout().toMillis(),
                    TimeUnit.MILLISECONDS)) {
                process.destroyForcibly();
                log.warn(
                        "event=python_search_failed query=\"{}\" topK={} "
                                + "durationMs={} errorType=timeout",
                        query, topK, elapsedMillis(startedAt)
                );
                throw new PythonSearchTimeoutException(
                        "The AI search engine timed out."
                );
            }
            String stdout = stdoutFuture.join();
            stderrFuture.join();
            if (process.exitValue() != 0) {
                log.warn(
                        "event=python_search_failed query=\"{}\" topK={} "
                                + "durationMs={} errorType=non_zero_exit exitCode={}",
                        query, topK, elapsedMillis(startedAt),
                        process.exitValue()
                );
                throw new PythonNonZeroExitException(
                        "The AI search engine failed.", process.exitValue()
                );
            }
            List<SearchResult> results;
            try {
                results = parseResults(stdout);
            } catch (PythonJsonParseException exception) {
                log.warn(
                        "event=python_search_failed query=\"{}\" topK={} "
                                + "durationMs={} errorType=invalid_json",
                        query, topK, elapsedMillis(startedAt)
                );
                throw exception;
            }
            log.info(
                    "event=python_search_succeeded query=\"{}\" topK={} "
                            + "resultCount={} durationMs={}",
                    query, topK, results.size(), elapsedMillis(startedAt)
            );
            return results;
        } catch (IOException exception) {
            log.warn(
                    "event=python_search_failed query=\"{}\" topK={} "
                            + "durationMs={} errorType=start_failure",
                    query, topK, elapsedMillis(startedAt)
            );
            throw new PythonProcessStartException(
                    "The AI search engine could not be started.", exception
            );
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            log.warn(
                    "event=python_search_failed query=\"{}\" topK={} "
                            + "durationMs={} errorType=interrupted",
                    query, topK, elapsedMillis(startedAt)
            );
            throw new PythonSearchInterruptedException(
                    "The AI search request was interrupted.", exception
            );
        } catch (CompletionException exception) {
            log.warn(
                    "event=python_search_failed query=\"{}\" topK={} "
                            + "durationMs={} errorType=output_read_failure",
                    query, topK, elapsedMillis(startedAt)
            );
            throw new PythonProcessStartException(
                    "The AI search engine output could not be read.",
                    exception.getCause()
            );
        }
    }

    private CompletableFuture<String> readStream(java.io.InputStream stream) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                return new String(stream.readAllBytes(), StandardCharsets.UTF_8);
            } catch (IOException exception) {
                throw new CompletionException(exception);
            }
        });
    }

    private List<SearchResult> parseResults(String output) {
        try {
            return Arrays.asList(objectMapper.readValue(output, SearchResult[].class));
        } catch (JsonProcessingException exception) {
            throw new PythonJsonParseException(
                    "The AI search engine returned an invalid response.", exception
            );
        }
    }

    private long elapsedMillis(long startedAt) {
        return (System.nanoTime() - startedAt) / 1_000_000;
    }
}
