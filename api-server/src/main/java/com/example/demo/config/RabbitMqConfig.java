package com.example.demo.config;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMqConfig {

	public static final String EXCHANGE_NAME = "ocr.jobs.exchange";
	public static final String QUEUE_NAME = "ocr.jobs";
	public static final String ROUTING_KEY = "ocr.jobs";

	@Bean
	TopicExchange ocrJobsExchange() {
		return new TopicExchange(EXCHANGE_NAME);
	}

	@Bean
	Queue ocrJobsQueue() {
		return new Queue(QUEUE_NAME, true);
	}

    @Bean
    Binding ocrJobsBinding(Queue ocrJobsQueue, TopicExchange ocrJobsExchange) {
        return BindingBuilder.bind(ocrJobsQueue)
                .to(ocrJobsExchange)
                .with(ROUTING_KEY);
    }
}
