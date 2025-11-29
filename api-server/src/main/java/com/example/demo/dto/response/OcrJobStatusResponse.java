package com.example.demo.dto.response;

import com.example.demo.entity.OcrJobStatus;

public record OcrJobStatusResponse(
		Long jobId,
		OcrJobStatus status
) {
}
