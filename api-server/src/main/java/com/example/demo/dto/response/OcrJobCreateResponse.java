package com.example.demo.dto.response;

import com.example.demo.entity.OcrJobStatus;

public record OcrJobCreateResponse(
		Long jobId,
		OcrJobStatus status
) {
}
