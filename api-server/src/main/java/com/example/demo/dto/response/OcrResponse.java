package com.example.demo.dto.response;

public record OcrResponse(
		String message,
		double latencyMs
) {

}
