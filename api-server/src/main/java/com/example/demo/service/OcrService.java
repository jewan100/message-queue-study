package com.example.demo.service;

import java.util.concurrent.CompletableFuture;

import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.example.demo.client.OcrWorkerClient;
import com.example.demo.client.OcrWorkerClientV2;
import com.example.demo.dto.request.OcrRequest;
import com.example.demo.dto.response.OcrJobCreateResponse;
import com.example.demo.dto.response.OcrJobStatusResponse;
import com.example.demo.dto.response.OcrResponse;
import com.example.demo.dto.response.OcrWorkerPredictResponse;
import com.example.demo.entity.OcrJob;
import com.example.demo.repository.OcrJobRepository;

import lombok.RequiredArgsConstructor;

@Service
@RequiredArgsConstructor
public class OcrService {

	private final OcrWorkerClient ocrWorkerClient;
	private final OcrWorkerClientV2 ocrWorkerClientV2;

	private final OcrJobRepository ocrJobRepository;

	public OcrResponse runSyncV0(OcrRequest request) {
		OcrWorkerPredictResponse workerRes = ocrWorkerClient.predict(request.pdfName());
		return new OcrResponse(workerRes.message());
	}

	@Async("ocrExecutor")
	public CompletableFuture<OcrResponse> runASyncV1(OcrRequest request) {
		OcrResponse response = runSyncV0(request);
		return CompletableFuture.completedFuture(response);
	}

	public OcrResponse runSyncV2(OcrRequest request) {
		OcrWorkerPredictResponse workerRes = ocrWorkerClientV2.predict(request.pdfName());
		return new OcrResponse(workerRes.message());
	}

	@Transactional
	public OcrJobCreateResponse createJobV3(OcrRequest request) {
		OcrJob savedJob = ocrJobRepository.save(OcrJob.createPendingJob(request.pdfName()));
		return new OcrJobCreateResponse(savedJob.getId(), savedJob.getStatus());
	}

	@Transactional(readOnly = true)
	public OcrJobStatusResponse getJobStatusV3(Long jobId) {
		OcrJob job = ocrJobRepository.findById(jobId)
				.orElseThrow(() -> new IllegalArgumentException("OCR Job not found. id=" + jobId));

		return new OcrJobStatusResponse(job.getId(), job.getStatus());
	}
}
