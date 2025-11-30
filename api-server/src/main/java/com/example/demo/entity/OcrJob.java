package com.example.demo.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "ocr_job")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class OcrJob {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 20)
	private OcrJobStatus status;

	@Column(name = "pdf_name", nullable = false, length = 255)
	private String pdfName;

	@Column(name = "created_at", nullable = false)
	private LocalDateTime createdAt;

	@Builder
	private OcrJob(OcrJobStatus status, String pdfName, LocalDateTime createdAt) {
		this.status = status;
		this.pdfName = pdfName;
		this.createdAt = createdAt;
	}

	public static OcrJob createPendingJob(String pdfName) {
		return OcrJob.builder().status(OcrJobStatus.PENDING).pdfName(pdfName).createdAt(LocalDateTime.now()).build();
	}
}
