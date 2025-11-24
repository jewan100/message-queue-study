import http from "k6/http";
import { check } from "k6";

const vus = __ENV.VUS ? parseInt(__ENV.VUS, 10) : 1;
const duration = __ENV.DURATION || "30s";
const iterationsEnv = __ENV.ITERATIONS;

export const options = iterationsEnv
  ? {
      vus,
      iterations: parseInt(iterationsEnv, 10),
    }
  : {
      vus,
      duration,
    };

export default function () {
  const url = "http://localhost:8080/api/v0/ocr/sync";
  const payload = JSON.stringify({ pdfName: "sample.pdf" });
  const params = {
    headers: { "Content-Type": "application/json" },
  };

  const res = http.post(url, payload, params);

  check(res, {
    "status is 200": (r) => r.status === 200,
  });
}
