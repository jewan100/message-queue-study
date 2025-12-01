package com.example.demo.client;

import java.util.HashMap;
import java.util.Map;

import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

import com.example.demo.config.RabbitMqConfig;

import lombok.RequiredArgsConstructor;

@Component("rabbitOcrJobQueueClient")
@RequiredArgsConstructor
public class RabbitOcrJobQueueClient implements OcrJobQueueClient {

	private final RabbitTemplate rabbitTemplate;

	@Override
	public void enqueue(Long jobId, String pdfName) {
		Map<String, String> fields = new HashMap<>();
		fields.put("jobId", String.valueOf(jobId));
		fields.put("pdfName", pdfName);
		fields.put("createdAt", String.valueOf(System.currentTimeMillis()));

		rabbitTemplate.convertAndSend(
                RabbitMqConfig.EXCHANGE_NAME,
                RabbitMqConfig.ROUTING_KEY,
                fields
        );
	}

}
