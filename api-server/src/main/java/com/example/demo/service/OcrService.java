package com.example.demo.service;

import java.util.concurrent.CompletableFuture;

import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import com.example.demo.client.OcrWorkerClient;
import com.example.demo.dto.request.OcrRequest;
import com.example.demo.dto.response.OcrResponse;
import com.example.demo.dto.response.OcrWorkerPredictResponse;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class OcrService {

	private final OcrWorkerClient ocrWorkerClient;

	public OcrResponse runSync(OcrRequest request) {
		OcrWorkerPredictResponse workerRes = ocrWorkerClient.predict(request.pdfName());
		return new OcrResponse(workerRes.message(), workerRes.latencyMs());
	}

	@Async("ocrExecutor")
	public CompletableFuture<OcrResponse> runASync(OcrRequest request) {
		OcrResponse response = runSync(request);
		return CompletableFuture.completedFuture(response);
	}

}
