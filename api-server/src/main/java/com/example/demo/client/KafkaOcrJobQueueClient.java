package com.example.demo.client;

import java.util.HashMap;
import java.util.Map;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import com.example.demo.config.KafkaProducerConfig;

import lombok.RequiredArgsConstructor;
import tools.jackson.databind.ObjectMapper;

@Component("kafkaOcrJobQueueClient")
@RequiredArgsConstructor
public class KafkaOcrJobQueueClient implements OcrJobQueueClient {

	private final KafkaTemplate<String, String> kafkaTemplate;
	private final ObjectMapper objectMapper;

	@Override
	public void enqueue(Long jobId, String pdfName) {
		Map<String, String> fields = new HashMap<>();
		fields.put("jobId", String.valueOf(jobId));
		fields.put("pdfName", pdfName);
		fields.put("createdAt", String.valueOf(System.currentTimeMillis()));

		try {
			String json = objectMapper.writeValueAsString(fields);
			kafkaTemplate.send(KafkaProducerConfig.TOPIC_NAME, json);
		} catch (Exception e) {
			throw new RuntimeException("Failed to publish job to Kafka", e);
		}
	}

}
