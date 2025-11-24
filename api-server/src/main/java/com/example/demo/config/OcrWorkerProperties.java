package com.example.demo.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "ocr.worker")
public record OcrWorkerProperties(
        String baseUrl,
        String predictPath,
        int connectTimeoutMs,
        int readTimeoutMs 
) {

}
