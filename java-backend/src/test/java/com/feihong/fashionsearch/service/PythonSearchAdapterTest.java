package com.feihong.fashionsearch.service;

import java.time.Duration;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import com.feihong.fashionsearch.config.PythonSearchProperties;
import com.feihong.fashionsearch.exception.PythonProcessStartException;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PythonSearchAdapterTest {
    @Test
    void mapsProcessStartupFailureToSpecificException() {
        PythonSearchProperties properties = new PythonSearchProperties(
                "definitely-missing-python-executable",
                ".",
                "scripts/search.py",
                Duration.ofSeconds(1)
        );
        PythonSearchAdapter adapter =
                new PythonSearchAdapter(properties, new ObjectMapper());

        assertThatThrownBy(() -> adapter.search("black dress", 5))
                .isInstanceOf(PythonProcessStartException.class)
                .hasMessage("The AI search engine could not be started.");
    }
}
