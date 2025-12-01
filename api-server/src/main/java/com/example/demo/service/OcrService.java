package com.example.demo.service;

import java.util.concurrent.CompletableFuture;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import com.example.demo.client.OcrJobQueueClient;
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

	@Qualifier("redisOcrJobQueueClient")
	private final OcrJobQueueClient redisOcrJobQueueClient;

	@Qualifier("rabbitOcrJobQueueClient")
	private final OcrJobQueueClient rabbitOcrJobQueueClient;

	@Qualifier("kafkaOcrJobQueueClient")
	private final OcrJobQueueClient kafkaOcrJobQueueClient;

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

	@Transactional
	public OcrJobCreateResponse createJobV4(OcrRequest request) {
		OcrJob savedJob = ocrJobRepository.save(OcrJob.createPendingJob(request.pdfName()));

		TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
			@Override
			public void afterCommit() {
				redisOcrJobQueueClient.enqueue(savedJob.getId(), savedJob.getPdfName());
			}
		});

		return new OcrJobCreateResponse(savedJob.getId(), savedJob.getStatus());
	}

	@Transactional
	public OcrJobCreateResponse createJobV5(OcrRequest request) {
		OcrJob savedJob = ocrJobRepository.save(OcrJob.createPendingJob(request.pdfName()));

		TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
			@Override
			public void afterCommit() {
				rabbitOcrJobQueueClient.enqueue(savedJob.getId(), savedJob.getPdfName());
			}
		});

		return new OcrJobCreateResponse(savedJob.getId(), savedJob.getStatus());
	}

	@Transactional
	public OcrJobCreateResponse createJobV6(OcrRequest request) {
		OcrJob savedJob = ocrJobRepository.save(OcrJob.createPendingJob(request.pdfName()));

		TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
			@Override
			public void afterCommit() {
				kafkaOcrJobQueueClient.enqueue(savedJob.getId(), savedJob.getPdfName());
			}
		});

		return new OcrJobCreateResponse(savedJob.getId(), savedJob.getStatus());
	}

	@Transactional(readOnly = true)
	public OcrJobStatusResponse getJobStatus(Long jobId) {
		OcrJob job = ocrJobRepository.findById(jobId)
				.orElseThrow(() -> new IllegalArgumentException("OCR Job not found. id=" + jobId));

		return new OcrJobStatusResponse(job.getId(), job.getStatus());
	}

}
