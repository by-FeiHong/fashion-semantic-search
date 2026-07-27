package com.feihong.fashionsearch.service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.stereotype.Service;

import com.feihong.fashionsearch.common.SearchServiceException;
import com.feihong.fashionsearch.config.PythonSearchProperties;
import com.feihong.fashionsearch.dto.SearchRequest;
import com.feihong.fashionsearch.dto.SearchResult;

@Service
public class PythonCliSearchService implements SearchService {
    private static final Pattern RESULT_PATTERN = Pattern.compile(
            "^\\d+\\. score=([\\d.-]+) item_id=(\\S+) split=\\S+\\R\\s+(.*)$",
            Pattern.MULTILINE
    );
    private final PythonSearchProperties properties;

    public PythonCliSearchService(PythonSearchProperties properties) {
        this.properties = properties;
    }

    @Override
    public List<SearchResult> search(SearchRequest request) {
        Path root = Path.of(properties.projectRoot()).toAbsolutePath().normalize();
        ProcessBuilder builder = new ProcessBuilder(
                properties.executable(), "scripts/search.py", request.query().trim(),
                "--top-k", String.valueOf(request.resolvedTopK())
        );
        builder.directory(root.toFile());
        builder.redirectErrorStream(true);
        try {
            Process process = builder.start();
            if (!process.waitFor(properties.timeoutSeconds(), TimeUnit.SECONDS)) {
                process.destroyForcibly();
                throw new SearchServiceException("Python search timed out.");
            }
            String output = new String(
                    process.getInputStream().readAllBytes(), StandardCharsets.UTF_8
            );
            if (process.exitValue() != 0) {
                throw new SearchServiceException("Python search failed: " + output.strip());
            }
            return parseResults(output);
        } catch (IOException exception) {
            throw new SearchServiceException(
                    "Unable to start the configured Python search process.", exception
            );
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new SearchServiceException("Python search was interrupted.", exception);
        }
    }

    private List<SearchResult> parseResults(String output) {
        List<SearchResult> results = new ArrayList<>();
        Matcher matcher = RESULT_PATTERN.matcher(output);
        while (matcher.find()) {
            results.add(new SearchResult(
                    matcher.group(2), Double.parseDouble(matcher.group(1)),
                    matcher.group(3).strip(), null, null
            ));
        }
        return results;
    }
}
