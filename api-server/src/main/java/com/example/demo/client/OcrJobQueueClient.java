package com.example.demo.client;

public interface OcrJobQueueClient {

	void enqueue(Long jobId, String pdfName);
}
