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
import org.springframework.stereotype.Component;

import com.feihong.fashionsearch.config.PythonSearchProperties;
import com.feihong.fashionsearch.dto.SearchResult;
import com.feihong.fashionsearch.exception.SearchServiceException;

@Component
public class PythonSearchAdapter {
    private final PythonSearchProperties properties;
    private final ObjectMapper objectMapper;

    public PythonSearchAdapter(
            PythonSearchProperties properties,
            ObjectMapper objectMapper
    ) {
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    public List<SearchResult> search(String query, int topK) {
        Path root = Path.of(properties.projectRoot()).toAbsolutePath().normalize();
        ProcessBuilder builder = new ProcessBuilder(
                properties.executable(),
                "scripts/search.py",
                query,
                "--top-k",
                String.valueOf(topK),
                "--json"
        );
        builder.directory(root.toFile());

        try {
            Process process = builder.start();
            CompletableFuture<String> stdoutFuture = readStream(process.getInputStream());
            CompletableFuture<String> stderrFuture = readStream(process.getErrorStream());
            if (!process.waitFor(properties.timeoutSeconds(), TimeUnit.SECONDS)) {
                process.destroyForcibly();
                throw new SearchServiceException("Python search timed out.");
            }
            String stdout = stdoutFuture.join();
            String stderr = stderrFuture.join();
            if (process.exitValue() != 0) {
                throw new SearchServiceException(
                        "Python search failed: " + stderr.strip()
                );
            }
            return parseResults(stdout);
        } catch (IOException exception) {
            throw new SearchServiceException(
                    "Unable to start the configured Python search process.", exception
            );
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new SearchServiceException("Python search was interrupted.", exception);
        } catch (CompletionException exception) {
            throw new SearchServiceException(
                    "Unable to read the Python search output.", exception.getCause()
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
            throw new SearchServiceException(
                    "Python search returned invalid JSON.", exception
            );
        }
    }
}
