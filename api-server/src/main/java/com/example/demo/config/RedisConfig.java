package com.example.demo.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.stream.ReadOffset;
import org.springframework.data.redis.core.StreamOperations;
import org.springframework.data.redis.core.StringRedisTemplate;

@Configuration
public class RedisConfig {

	private static final Logger log = LoggerFactory.getLogger(RedisConfig.class);

	public static final String STREAM_KEY = "ocr:jobs";
	public static final String GROUP_NAME = "ocr-workers";

	@Bean
	StringRedisTemplate stringRedisTemplate(RedisConnectionFactory connectionFactory) {
		return new StringRedisTemplate(connectionFactory);
	}

	@Bean
	ApplicationRunner redisStreamInitializer(StringRedisTemplate stringRedisTemplate) {
		return args -> {
			StreamOperations<String, Object, Object> streamOps = stringRedisTemplate.opsForStream();

			try {
				streamOps.createGroup(STREAM_KEY, ReadOffset.latest(), GROUP_NAME);

				log.info("[Redis] Consumer group created. streamKey={}, groupName={}", STREAM_KEY, GROUP_NAME);
			} catch (Exception e) {
				Throwable root = e;
				while (root.getCause() != null) {
					root = root.getCause();
				}
				String rootMsg = root.getMessage();
				if (rootMsg != null && rootMsg.contains("BUSYGROUP")) {
					log.info("[Redis] Consumer group already exists. streamKey={}, groupName={}", STREAM_KEY,
							GROUP_NAME);
					return;
				}
				log.error("[Redis] Failed to create consumer group. streamKey={}, groupName={}, error={}", STREAM_KEY,
						GROUP_NAME, rootMsg, e);
			}
		};
	}
}
