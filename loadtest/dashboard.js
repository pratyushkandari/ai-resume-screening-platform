// k6 load test of the recruiter dashboard endpoint: GET /api/jobs/{id}/summary.
// The full procedure (seeding 10,000 resumes, cached vs. uncached runs) is in the README.
//
//   docker run --rm -i --add-host=host.docker.internal:host-gateway \
//     -e BASE_URL=http://host.docker.internal -e EMAIL=... -e PASSWORD=... -e JOB_ID=... \
//     grafana/k6:0.57.0 run - < loadtest/dashboard.js
//
// Optional: VUS (concurrent users, default 10) and DURATION (default 30s).
import http from "k6/http";
import { check } from "k6";
import { Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost";
const cacheHits = new Rate("summary_cache_hits");
const responseBytes = new Trend("summary_response_bytes");

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURATION || "30s",
  summaryTrendStats: ["avg", "med", "p(95)", "max"],
  thresholds: { http_req_failed: ["rate<0.01"] },
};

// Log in once for all virtual users, so the login rate limit is not part of the test.
export function setup() {
  const res = http.post(
    `${BASE_URL}/api/login`,
    JSON.stringify({ email: __ENV.EMAIL, password: __ENV.PASSWORD }),
    { headers: { "Content-Type": "application/json" } }
  );
  if (res.status !== 200) throw new Error(`login failed with ${res.status}: ${res.body}`);
  return { token: res.json("access_token") };
}

export default function (data) {
  const res = http.get(`${BASE_URL}/api/jobs/${__ENV.JOB_ID}/summary`, {
    headers: { Authorization: `Bearer ${data.token}` },
  });
  check(res, { "status is 200": (r) => r.status === 200 });
  cacheHits.add(res.headers["X-Cache"] === "HIT");
  responseBytes.add(res.body ? res.body.length : 0);
}
