package com.example.demo.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;

public record OcrWorkerPredictRequest(
		@JsonProperty("pdf_name") String pdfName
) {
	
}
