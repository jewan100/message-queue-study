package com.example.demo.client;

import java.util.HashMap;
import java.util.Map;

import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

import com.example.demo.config.RabbitMqConfig;

import lombok.RequiredArgsConstructor;
import tools.jackson.databind.ObjectMapper;

@Component("rabbitOcrJobQueueClient")
@RequiredArgsConstructor
public class RabbitOcrJobQueueClient implements OcrJobQueueClient {

	private final RabbitTemplate rabbitTemplate;
	private final ObjectMapper objectMapper;

	@Override
	public void enqueue(Long jobId, String pdfName) {
		Map<String, String> fields = new HashMap<>();
		fields.put("jobId", String.valueOf(jobId));
		fields.put("pdfName", pdfName);
		fields.put("createdAt", String.valueOf(System.currentTimeMillis()));

        try {
            String json = objectMapper.writeValueAsString(fields);

            rabbitTemplate.convertAndSend(
                    RabbitMqConfig.EXCHANGE_NAME,
                    RabbitMqConfig.ROUTING_KEY,
                    json
            );
        } catch (Exception e) {
            throw new RuntimeException("Failed to publish job to RabbitMQ", e);
        }
	}

}
