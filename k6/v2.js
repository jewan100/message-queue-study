import http from "k6/http";
import { check } from "k6";

const BASE_URL = "http://localhost:8080/api/v2/ocr";
const PDF_NAME = "sample.pdf";

const vus = __ENV.VUS ? parseInt(__ENV.VUS, 10) : 1;
const duration = __ENV.DURATION || "30s";
const iterationsEnv = __ENV.ITERATIONS;

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
  const url = `${BASE_URL}/sync`;

  const payload = JSON.stringify({ pdfName: PDF_NAME });

  const params = {
    headers: { "Content-Type": "application/json" },
    timeout: "60s",
  };

  const res = http.post(url, payload, params);

  check(res, {
    "status is 200": (r) => r.status === 200,
  });
}
