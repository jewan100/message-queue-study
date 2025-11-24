package com.example.demo.controller;

import java.util.concurrent.CompletableFuture;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.demo.dto.request.OcrRequest;
import com.example.demo.dto.response.OcrResponse;
import com.example.demo.service.OcrService;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/ocr")
@Slf4j
public class OcrControllerV1 {

	private final OcrService ocrService;

	@PostMapping("/sync")
	public CompletableFuture<ResponseEntity<OcrResponse>> post(@RequestBody OcrRequest request) {
		return ocrService.runASync(request).thenApply(response -> {
			return ResponseEntity.ok(response);
		});
	}

}
