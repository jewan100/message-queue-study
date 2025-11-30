import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = "http://localhost:8080/api/v3/ocr";
const PDF_NAME = "sample.pdf";

const vus = __ENV.VUS ? parseInt(__ENV.VUS, 10) : 1;
const duration = __ENV.DURATION || "30s";
const iterationsEnv = __ENV.ITERATIONS;

const MAX_POLL_SECONDS = __ENV.MAX_POLL_SECONDS
  ? parseInt(__ENV.MAX_POLL_SECONDS, 10)
  : 70;

const POLL_INTERVAL_SECONDS = __ENV.POLL_INTERVAL_SECONDS
  ? parseFloat(__ENV.POLL_INTERVAL_SECONDS)
  : 1;

export const options = iterationsEnv
  ? {
      vus,
      iterations: parseInt(iterationsEnv, 10),
      thresholds: {
        http_req_duration: ["p(95)<60000"],
        http_req_failed: ["rate==0"],
      },
    }
  : {
      vus,
      duration,
      thresholds: {
        http_req_duration: ["p(95)<60000"],
        http_req_failed: ["rate==0"],
      },
    };

export default function () {
  const createPayload = JSON.stringify({ pdfName: PDF_NAME });

  const params = {
    headers: { "Content-Type": "application/json" },
    timeout: "10s",
  };

  const createRes = http.post(`${BASE_URL}/jobs`, createPayload, params);

  if (createRes.status !== 200) {
    return;
  }

  const body = createRes.json();
  const jobId = body.jobId;

  if (jobId === undefined || jobId === null) {
    return;
  }

  const start = Date.now();
  let finalStatus = null;

  while (true) {
    const elapsedSec = (Date.now() - start) / 1000;

    if (elapsedSec > MAX_POLL_SECONDS) {
      finalStatus = "TIMEOUT";
      break;
    }

    const statusRes = http.get(`${BASE_URL}/jobs/${jobId}`, {
      timeout: "10s",
    });

    if (statusRes.status !== 200) {
      finalStatus = "HTTP_ERROR";
      break;
    }

    const statusBody = statusRes.json();
    const status = statusBody.status;

    if (status === "PENDING" || status === "PROCESSING") {
      sleep(POLL_INTERVAL_SECONDS);
      continue;
    }

    finalStatus = status;
    break;
  }

  check(
    { finalStatus },
    {
      "job finished with DONE": (v) => v.finalStatus === "DONE",
    }
  );
}
