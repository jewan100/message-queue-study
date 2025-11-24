package com.example.demo.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;

public record OcrWorkerPredictResponse(
		String message,
		
		@JsonProperty("latency_ms")
		double latencyMs
) {

}
