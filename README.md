# message-queue-study

Message Queue(DB, Redis, RabbitMQ, Kafka)를 이용한 **비동기 Job 처리**와  
Worker(Consumer) 개수(1/2/4)에 따른 **동시성·성능·안정성**을 실험하는 레포지토리입니다.

워크로드는 단순화된 **OCR 모델 `predict()` 호출**로 고정하고,  
아키텍처만 단계적으로 바꾸면서 “어디까지 버티는지 / 어디서 터지는지”를 비교합니다.

---

## 1. 목표

- 동기 vs 비동기 아키텍처의 차이를 **숫자(RPS, 지연, 에러율)** 로 비교
- DB/Redis/RabbitMQ/Kafka를 이용한 **Job 큐 패턴** 공부
- Worker(Consumer) **1/2/4개 스케일링**이 처리량/응답시간에 미치는 영향 관찰
- Backpressure(요청 거절) 유무에 따른 **시스템 안정성 차이** 비교

---

## 2. 아키텍처 개요

구성 요소:

- **API 서버 (Producer)**
  - Spring Boot 기반
  - 클라이언트 요청을 받아 동기 처리 또는 Job 생성 후 큐에 enqueue
- **Worker / OCR 서버 (Consumer)**
  - Python 기반
  - 큐(DB/Redis/RabbitMQ/Kafka)에서 Job을 소비하고 `model.predict()` 실행
- **DB (PostgreSQL)**
  - `jobs` 테이블에 Job 상태/결과 저장
  - V3에서는 **DB 자체가 큐 역할**
- **Message Queue / Broker**
  - V4: Redis
  - V5: RabbitMQ
  - V6: Kafka
- **모니터링**
  - Prometheus + Grafana
  - API/Worker/Queue/리소스 사용량 시각화
- **부하 테스트**
  - k6 스크립트로 버전별 엔드포인트 부하

---

## 3. 버전(V0 ~ V6) 개요

### 3.1 버전별 아키텍처 요약

| 버전 | 엔드포인트(주요)    | 큐            | Worker 구조                 | 핵심 포인트                             |
| ---- | ------------------- | ------------- | --------------------------- | --------------------------------------- |
| V0   | `POST /v0/ocr/sync` | 없음          | 없음 (API → OCR 동기)       | 완전 동기 + 스레드 풀만으로 버티기      |
| V1   | `POST /v1/ocr/sync` | 없음          | 없음 (내부 비동기)          | 스프링 내부 비동기(Executor) 효과       |
| V2   | `POST /v2/ocr/sync` | 없음          | OCR 서버 N대(2/4) 직접 호출 | 큐 없이 **인스턴스만 늘렸을 때** 한계   |
| V3   | `POST /v3/ocr/jobs` | DB (Postgres) | Python Worker 1/2/4         | DB를 큐처럼(`PENDING` 행) 사용하는 패턴 |
| V4   | `POST /v4/ocr/jobs` | Redis         | Python Worker 1/2/4         | 인메모리 큐(빠른 pickup) 도입 효과      |
| V5   | `POST /v5/ocr/jobs` | RabbitMQ      | Python Worker 1/2/4         | 정통 MQ(ack/retry) 도입                 |
| V6   | `POST /v6/ocr/jobs` | Kafka         | Python Worker 1/2/4         | 스트림/로그 기반 브로커, 컨슈머 그룹    |

### 3.2 공통 도메인

모든 비동기 버전(V3~V6)에서 아래 도메인을 공유합니다.

- `Job`
  - `id` (UUID)
  - `status` (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, …)
  - `inputPath` / `outputPath`
  - `errorMessage`
  - `createdAt`, `updatedAt`
- `JobStatus` enum
- `JobRepository` (Spring Data JPA)
- `OcrJobService`
  - `createJob(CreateJobRequest)`
  - `getJobStatus(jobId)`

큐/브로커별 차이는 `JobQueuePort` 인터페이스 구현체로 분리합니다.

---

## 4. 기술 스택

| 구분            | 기술                                               | 비고                                   |
| --------------- | -------------------------------------------------- | -------------------------------------- |
| 언어(API)       | Java 21                                            |                                        |
| 프레임워크(API) | Spring Boot 3.x (MVC)                              | Web, Actuator, JPA                     |
| ORM/DB 연동     | Spring Data JPA                                    |                                        |
| DB              | PostgreSQL                                         | Job 저장 + V3에서 DB 큐                |
| 언어(Worker)    | Python 3.x                                         | FastAPI(동기용), 워커 스크립트(비동기) |
| OCR             | 단순 `model.predict()`                             | 병목 역할만 수행                       |
| MQ(V4)          | Redis                                              | 인메모리 큐                            |
| MQ(V5)          | RabbitMQ                                           | AMQP, 큐/익스체인지                    |
| MQ(V6)          | Kafka                                              | 토픽 + 컨슈머 그룹                     |
| 메시징(Java)    | spring-data-redis, spring-amqp, spring-kafka       | 버전별 사용                            |
| 모니터링        | Prometheus + Grafana                               | API/Worker/Queue/리소스 메트릭         |
| 메트릭(API)     | Spring Actuator + Micrometer + Prometheus Registry | `/actuator/prometheus`                 |
| 메트릭(Worker)  | prometheus-client (Python)                         | `/metrics` HTTP 서버                   |
| 부하 테스트     | k6                                                 | JS 스크립트로 버전별 부하 테스트       |
| 컨테이너        | Docker + docker-compose                            | 전체 구성요소 로컬에서 실행            |
