package com.feihong.fashionsearch.config;

import java.time.Duration;

import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;

import static org.assertj.core.api.Assertions.assertThat;

class AiServicePropertiesTest {
    private final ApplicationContextRunner contextRunner =
            new ApplicationContextRunner()
                    .withUserConfiguration(TestConfiguration.class)
                    .withPropertyValues(
                            "fashion-search.ai-service.base-url=http://localhost:9000",
                            "fashion-search.ai-service.connect-timeout=2s",
                            "fashion-search.ai-service.read-timeout=12s"
                    );

    @Test
    void bindsAiServiceConfiguration() {
        contextRunner.run(context -> {
            AiServiceProperties properties = context.getBean(AiServiceProperties.class);
            assertThat(properties.baseUrl()).isEqualTo("http://localhost:9000");
            assertThat(properties.connectTimeout()).isEqualTo(Duration.ofSeconds(2));
            assertThat(properties.readTimeout()).isEqualTo(Duration.ofSeconds(12));
        });
    }

    @Configuration(proxyBeanMethods = false)
    @EnableConfigurationProperties(AiServiceProperties.class)
    static class TestConfiguration { }
}
