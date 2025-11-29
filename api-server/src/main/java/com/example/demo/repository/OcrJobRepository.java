package com.example.demo.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.demo.entity.OcrJob;

public interface OcrJobRepository extends JpaRepository<OcrJob, Long> {
}
