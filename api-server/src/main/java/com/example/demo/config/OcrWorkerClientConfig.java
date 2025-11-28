package com.example.demo.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration
@EnableConfigurationProperties(OcrWorkerProperties.class)
public class OcrWorkerClientConfig {

	@Bean
	RestClient ocrRestClient(OcrWorkerProperties props) {
		var factory = new SimpleClientHttpRequestFactory();
		factory.setConnectTimeout(props.connectTimeoutMs());
		factory.setReadTimeout(props.readTimeoutMs());
		
		return RestClient.builder()
				// .baseUrl(props.baseUrl())
				.requestFactory(factory)
				.build();
	}
}
