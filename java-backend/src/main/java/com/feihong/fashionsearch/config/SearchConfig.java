package com.feihong.fashionsearch.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties({
        PythonSearchProperties.class,
        SearchCacheProperties.class
})
public class SearchConfig {
}
