package com.example.demo.client;

import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.example.demo.config.OcrWorkerProperties;
import com.example.demo.dto.request.OcrWorkerPredictRequest;
import com.example.demo.dto.response.OcrWorkerPredictResponse;

import lombok.RequiredArgsConstructor;

@Component
@RequiredArgsConstructor
public class OcrWorkerClientV2 {

	private final RestClient restClient;
	private final OcrWorkerProperties properties;
	
	private final AtomicInteger counter = new AtomicInteger(0);
	
	private String nextBaseUrl() {
		List<String> nodes = properties.nodes();
		int idx = Math.floorMod(counter.getAndIncrement(), nodes.size());
		return nodes.get(idx);
	}
	
	public OcrWorkerPredictResponse predict(String pdfName) {
		var requestBody = new OcrWorkerPredictRequest(pdfName);
		
        String baseUrl = nextBaseUrl();
        String url = baseUrl + properties.predictPath();
		
		return restClient
				.post()
				.uri(url)
				.body(requestBody)
				.retrieve()
				.body(OcrWorkerPredictResponse.class);
	}
}
