package com.example.demo.service;

import java.util.concurrent.CompletableFuture;

import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import com.example.demo.client.OcrWorkerClient;
import com.example.demo.client.OcrWorkerClientV2;
import com.example.demo.dto.request.OcrRequest;
import com.example.demo.dto.response.OcrResponse;
import com.example.demo.dto.response.OcrWorkerPredictResponse;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class OcrService {

	private final OcrWorkerClient ocrWorkerClient;
	private final OcrWorkerClientV2 ocrWorkerClientV2;

	public OcrResponse runSyncV0(OcrRequest request) {
		OcrWorkerPredictResponse workerRes = ocrWorkerClient.predict(request.pdfName());
		return new OcrResponse(workerRes.message(), workerRes.latencyMs());
	}

	@Async("ocrExecutor")
	public CompletableFuture<OcrResponse> runASyncV1(OcrRequest request) {
		OcrResponse response = runSyncV0(request);
		return CompletableFuture.completedFuture(response);
	}

	public OcrResponse runSyncV2(OcrRequest request) {
		OcrWorkerPredictResponse workerRes = ocrWorkerClientV2.predict(request.pdfName());
		return new OcrResponse(workerRes.message(), workerRes.latencyMs());
	}
}
