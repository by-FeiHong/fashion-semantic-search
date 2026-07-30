package com.feihong.fashionsearch.config;

import java.time.Duration;

import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;

import static org.assertj.core.api.Assertions.assertThat;

class PythonSearchPropertiesTest {
    private final ApplicationContextRunner contextRunner =
            new ApplicationContextRunner()
                    .withUserConfiguration(TestConfiguration.class)
                    .withPropertyValues(
                            "fashion-search.python.executable=python-test",
                            "fashion-search.python.project-root=C:/project",
                            "fashion-search.python.search-script=tools/search.py",
                            "fashion-search.python.timeout=12s"
                    );

    @Test
    void bindsPythonSearchConfiguration() {
        contextRunner.run(context -> {
            PythonSearchProperties properties =
                    context.getBean(PythonSearchProperties.class);
            assertThat(properties.executable()).isEqualTo("python-test");
            assertThat(properties.projectRoot()).isEqualTo("C:/project");
            assertThat(properties.searchScript()).isEqualTo("tools/search.py");
            assertThat(properties.timeout()).isEqualTo(Duration.ofSeconds(12));
        });
    }

    @Configuration(proxyBeanMethods = false)
    @EnableConfigurationProperties(PythonSearchProperties.class)
    static class TestConfiguration {
    }
}
