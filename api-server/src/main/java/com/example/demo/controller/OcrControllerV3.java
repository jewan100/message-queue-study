package com.example.demo.controller;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.demo.dto.request.OcrRequest;
import com.example.demo.dto.response.OcrJobCreateResponse;
import com.example.demo.dto.response.OcrJobStatusResponse;
import com.example.demo.service.OcrService;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v3/ocr")
@Slf4j
public class OcrControllerV3 {

	private final OcrService ocrService;

	@PostMapping("/jobs")
	public ResponseEntity<OcrJobCreateResponse> post(@RequestBody OcrRequest request) {
		OcrJobCreateResponse response = ocrService.createJobV3(request);
		return ResponseEntity.ok(response);
	}

	@GetMapping("/jobs/{jobId}")
	public ResponseEntity<OcrJobStatusResponse> getJobStatus(@PathVariable("jobId") Long jobId) {
		OcrJobStatusResponse response = ocrService.getJobStatusV3(jobId);
		return ResponseEntity.ok(response);
	}
}
