package com.example.demo.client;

import java.util.HashMap;
import java.util.Map;

import org.springframework.data.redis.connection.stream.MapRecord;
import org.springframework.data.redis.connection.stream.StreamRecords;
import org.springframework.data.redis.core.StreamOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import com.example.demo.config.RedisConfig;

import lombok.RequiredArgsConstructor;

@Component("redisOcrJobQueueClient")
@RequiredArgsConstructor
public class RedisOcrJobQueueClient implements OcrJobQueueClient {

	private final StringRedisTemplate redisTemplate;

	@Override
	public void enqueue(Long jobId, String pdfName) {
		Map<String, String> fields = new HashMap<>();
		fields.put("jobId", String.valueOf(jobId));
		fields.put("pdfName", pdfName);
		fields.put("createdAt", String.valueOf(System.currentTimeMillis()));

		StreamOperations<String, String, String> streamOps = redisTemplate.opsForStream();
		
		MapRecord<String, String, String> record = StreamRecords
				.newRecord()
				.in(RedisConfig.STREAM_KEY)
				.ofMap(fields);

		streamOps.add(record);
	}

}
