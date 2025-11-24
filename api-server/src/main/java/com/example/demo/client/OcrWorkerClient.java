package com.example.demo.client;

import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.example.demo.config.OcrWorkerProperties;
import com.example.demo.dto.request.OcrWorkerPredictRequest;
import com.example.demo.dto.response.OcrWorkerPredictResponse;

import lombok.RequiredArgsConstructor;

@Component
@RequiredArgsConstructor
public class OcrWorkerClient {

	private final RestClient restClient;
	private final OcrWorkerProperties properties;
	
	public OcrWorkerPredictResponse predict(String pdfName) {
		var requestBody = new OcrWorkerPredictRequest(pdfName);
		
		return restClient
				.post()
				.uri(properties.predictPath())
				.body(requestBody)
				.retrieve()
				.body(OcrWorkerPredictResponse.class);
	}
	
	
}
