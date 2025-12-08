# message-queue-study

DB / Redis / RabbitMQ / Kafka를 이용해 **비동기 Job 처리 파이프라인**을 구현하고,  
Worker(Consumer) 개수(1/2/4)에 따라 **동시성 / 성능 / 안정성**을 실험하는 레포지토리입니다.

워크로드는 의도적으로 CPU-heavy 한 **OCR 파이프라인(`run_ocr`) 호출**로 고정하고,  
아키텍처만 단계적으로 바꾸면서 “구조를 바꿔도 실제로 뭐가 달라지는지”를 확인합니다.

---

## 1. 목표

- 동기 vs 비동기 아키텍처의 차이를 **지연 시간, 에러율, 처리량(req/s)** 으로 비교
- DB / Redis / RabbitMQ / Kafka 를 이용한 **Job 큐 패턴** 학습
- Worker(Consumer)를 1/2/4개로 늘렸을 때의 **처리량 변화 / 안정성 변화** 관찰
- 실험 결과,
  - 현재 워크로드에서는 MQ·DB·구조보다 **OCR 연산 자체가 절대 병목**이라는 점을 확인하는 것이 1차 결론

---

## 2. 아키텍처 개요

구성 요소:

- **API 서버 (Producer)**
  - Spring Boot 기반
  - 클라이언트 요청을 받아:
    - V0~V2: 동기/비동기로 바로 OCR 서버 호출
    - V3~V6: Job을 생성하고 각각 다른 큐(DB / Redis / RabbitMQ / Kafka)에 enqueue
- **Worker / OCR 서버 (Consumer)**
  - Python 기반
  - 버전별로 다른 큐에서 Job을 가져와 `run_ocr(PredictRequest)` 실행
  - 결과를 DB에 업데이트 (`DONE` / `FAILED` 등)
- **DB (PostgreSQL)**
  - `ocr_job` 테이블에 Job 상태/결과 저장
  - V3에서는 **DB 자체가 큐 역할**을 수행 (`PENDING` → `PROCESSING` → `DONE/FAILED`)
- **Message Queue / Broker**
  - V4: Redis Streams (`XADD` / `XREADGROUP`)
  - V5: RabbitMQ (queue + ack)
  - V6: Kafka (topic + consumer group, partition 기반 분산)
- **부하 테스트**
  - k6 스크립트로 각 버전의 `/vX/ocr/...` 엔드포인트에 부하를 걸고
  - VUS(동시 사용자), ITERATIONS(총 요청 수), duration(지속 시간)을 조합해 성능 측정

---

## 3. 버전(V0 ~ V6) 개요

### 3.1 버전별 아키텍처 요약

| 버전 | 엔드포인트(주요)    | 큐 / 브로커   | Worker 구조                           | 핵심 포인트                                         |
| ---- | ------------------- | ------------ | ------------------------------------- | --------------------------------------------------- |
| V0   | `POST /v0/ocr/sync` | 없음         | 없음 (API → FastAPI(OCR) 동기 호출)   | 완전 동기 구조, API 스레드가 직접 OCR을 기다림      |
| V1   | `POST /v1/ocr/sync` | 없음         | 없음 (내부 비동기)                    | Spring 비동기(Executor)로 호출 구조만 변경          |
| V2   | `POST /v2/ocr/sync` | 없음         | OCR 서버 N대(1/2/4) 직접 HTTP 호출    | 큐 없이 **OCR 인스턴스 수만 늘렸을 때** 효과 확인    |
| V3   | `POST /v3/ocr/jobs` | DB (Postgres)| Python Worker 1/2/4                   | DB를 큐처럼(`PENDING` Job을 `SELECT FOR UPDATE`) 사용 |
| V4   | `POST /v4/ocr/jobs` | Redis Streams| Python Worker 1/2/4                   | 인메모리 스트림으로 빠른 pickup + Consumer Group    |
| V5   | `POST /v5/ocr/jobs` | RabbitMQ     | Python Worker 1/2/4                   | 정통 MQ(ack/requeue) 기반 분산 처리                 |
| V6   | `POST /v6/ocr/jobs` | Kafka        | Python Worker 1/2/4                   | 토픽 + 파티션 + 컨슈머 그룹 기반 분산 처리          |

---

## 4. 기술 스택

| 구분            | 기술                                  | 비고                                             |
| --------------- | ------------------------------------- | ------------------------------------------------ |
| 언어(API)       | Java 21                               |                                                  |
| 프레임워크(API) | Spring Boot 4.0 (MVC)                 | Web, Actuator, JPA                               |
| ORM/DB 연동     | Spring Data JPA                       | PostgreSQL                                       |
| DB              | PostgreSQL 18-alpine                  | `ocr_job` 테이블 + V3에서 큐 역할                |
| 언어(Worker)    | Python 3.x                            |                                                  |
| OCR             | `ocr_engine.run_ocr(PredictRequest)`  | CPU-heavy 워크로드, 의도적으로 병목 역할         |
| MQ(V4)          | Redis 8-alpine                        | Redis Streams (`XADD` / `XREADGROUP`)            |
| MQ(V5)          | RabbitMQ 4.2.1                        | Management 플러그인으로 UI 모니터링              |
| MQ(V6)          | Kafka (Confluent 이미지)              | Zookeeper + Kafka + Kafdrop                     |
| 메시징(Java)    | spring-data-redis                     | V4                                               |
| 메시징(Java)    | spring-amqp                           | V5                                               |
| 메시징(Java)    | spring-kafka                          | V6                                               |
| 부하 테스트     | k6                                    | 버전별 JS 스크립트 (`v0.js` ~ `v6.js`)           |
| 컨테이너        | Docker + docker-compose               | Postgres / Redis / RabbitMQ / Kafka 등          |

---

## 5. 현재까지 얻은 인사이트

### 5.1 OCR 워크로드 관점 (GPU → CPU 전환)

- 이 레포지토리의 **V0 ~ V6 전 버전**은 같은 OCR 파이프라인을 사용합니다.
- 초반에는 OCR이 **GPU**로 동작했고, 이 환경에서는:
  - GPU가 사실상 **한 번에 하나의 Job만 처리하는 병목 자원**처럼 동작해서
  - 워커 수를 늘려도, 결국 GPU 앞에서 **직렬 처리**가 일어났습니다.
- 이후 OCR을 **CPU 연산으로 전환**하자:
  - 워커 프로세스를 1 → 2 → 4개로 늘릴 때,
  - 서로 다른 CPU 코어에서 병렬로 돌아가면서 **동시에 처리 가능한 Job 개수가 워커 수에 비례해서 증가**했습니다.
  - 동일한 부하(VUS)에서 전체 처리 완료 시간이 눈에 띄게 줄고, 타임아웃/실패 비율도 낮아지는 효과가 있었습니다.

### 5.2 V3 ~ V6 (DB / Redis / RabbitMQ / Kafka) 요약

- V3(DB 큐), V4(Redis Streams), V5(RabbitMQ), V6(Kafka) 모두:
  - **API 서버는 Job만 생성하고 바로 반환**해서, 클라이언트 응답시간은 꽤 안정적으로 유지됩니다.
  - 실제 무거운 OCR 처리는 워커 쪽에서 비동기로 처리합니다.
- 현재 워크로드에서는:
  - 네 가지 큐/브로커(DB, Redis, RabbitMQ, Kafka) 간에 **지연시간 차이는 상대적으로 작습니다.**
- 구체적으로:
  - **DB 큐(V3)**  
    - 구현은 단순하지만, `PENDING` / `PROCESSING` 행을 락으로 뽑는 구조라  
      부하가 커지면 DB 락 경합과 인덱스 스캔 비용이 부담이 됩니다.
  - **Redis Streams(V4)**  
    - 인메모리라 Job pickup 속도는 빠르고, Consumer Group으로 워커 분산이 쉽습니다.
  - **RabbitMQ(V5)**  
    - 가장 전통적인 “메시지 큐”에 가까운 모델로, ack/requeue, dead-letter 등으로  
      **재시도·유실 방지·Backpressure** 컨트롤이 명확합니다.
  - **Kafka(V6)**  
    - 스트림/로그 기반이라 “Job 큐”라기보단 “이벤트 스트림”에 가깝지만,  
      컨슈머 그룹 + 파티션 설계로 워커 수를 선형에 가깝게 확장할 수 있습니다.

---

## 6. 실험 결과 요약 (정상 처리 vs 오류 비율)

> 공통 조건  
> - 입력: `pdfName = sample.pdf`  
> - k6: `VUS = ITERATIONS`, 그 중 **VUS=16, ITERATIONS=16** 시나리오를 대표 지표로 사용  
> - 오류에는 HTTP 에러 + 60초 초과 타임아웃을 모두 포함  
> - 대상 버전: **V3(DB 큐), V4(Redis Streams), V5(RabbitMQ), V6(Kafka)**

### 6.1 큐 기반 구조(V3 ~ V6, VUS=16 기준)

V3(DB 큐), V4(Redis Streams), V5(RabbitMQ), V6(Kafka) 모두에서 공통적인 처리 흐름은 다음과 같습니다.

1. API 서버에서 Job 생성 (`PENDING`)
2. 각 버전별 큐/브로커(DB / Redis / RabbitMQ / Kafka)에 Job enqueue
3. Python Worker가 Job을 가져와 `run_ocr(PredictRequest)` 실행
4. 결과를 DB에 `DONE` / `FAILED` 로 업데이트

실측 결과, **큐 종류(DB / Redis / RabbitMQ / Kafka)에 따른 차이보다  
Worker 개수에 따른 차이가 훨씬 지배적**이라, V3~V6 전체를 아래와 같이 **공통 패턴**으로 요약했습니다.

> 조건: 각 버전(V3~V6)에서 VUS=16, ITERATIONS=16 실행 시 통계

| Worker 수 | 정상 처리(건 / 비율) | 오류·타임아웃(건 / 비율) | 비고                                                 |
|-----------|----------------------|---------------------------|------------------------------------------------------|
| 1         | 4 / **25.0%**        | 12 / **75.0%**            | 단일 워커, 큐 종류와 상관없이 실패 비율이 높게 유지  |
| 2         | 6 / **37.5%**        | 10 / **62.5%**            | 워커 2개로 늘리면 성공 비율이 눈에 띄게 개선         |
| 4         | 8 / **50.0%**        | 8 / **50.0%**             | 워커 4개에서 성공/실패가 1:1 수준까지 개선           |

요약:

- 큐를 도입한(V3~V6) 시점부터는,  
  **“요청을 얼마나 빨리 받아서 저장하느냐”** 는 대부분 해결되고,
  실제 정상 처리 여부는 **OCR 워커 처리 능력**에 의해 결정됩니다.
- DB / Redis / RabbitMQ / Kafka 간에는
  - 동일한 워크로드에서 **성공률/실패율 차이가 크지 않았고**,
  - 대신 **Worker 수(1 → 2 → 4)를 얼마나 늘렸는지**가  
    정상 처리 비율을 **25% → 37.5% → 50%** 수준으로 끌어올리는 핵심 요인이었습니다.
