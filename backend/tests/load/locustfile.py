"""Locust load test — verify rate limit enforcement against a running server.

§13.7: Manual load testing for slowapi rate limits.

Usage:
    pip install locust
    cd backend
    # Start the server first:
    #   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    # Then run locust:
    locust -f tests/load/locustfile.py --headless -u 5 -r 1 -t 30s --host http://localhost:8000

    -u 5   : 5 concurrent users
    -r 1   : spawn 1 user per second
    -t 30s : run for 30 seconds
    --headless : no web UI (CLI output only)

Expected behavior:
    - /health requests always succeed (no rate limit)
    - /api/v1/job-postings/ingest hits 429 after 10 requests/minute
    - /api/v1/chat/messages hits 429 after 10 requests/minute

    The test PASSES if 429 responses appear for rate-limited endpoints
    while /health remains 100% successful.

Prerequisites:
    - RATE_LIMIT_ENABLED=true (default)
    - Server running on the specified --host
"""

from locust import HttpUser, between, task


class RateLimitUser(HttpUser):
    """Simulates a user hitting rate-limited endpoints.

    Assumes AUTH_ENABLED=false (local-first mode). When auth is enabled,
    add an Authorization header via on_start() or a headers dict.
    """

    wait_time = between(0.1, 0.5)

    @task(1)
    def health_check(self) -> None:
        """Baseline: /health is not rate-limited, should always succeed."""
        self.client.get("/health")

    @task(3)
    def ingest_job_posting(self) -> None:
        """POST /api/v1/job-postings/ingest — rate limited at 10/minute.

        Sends a minimal (invalid) body to trigger the rate limiter.
        The endpoint will return 422 (validation error) within the limit
        and 429 (rate limited) when the limit is exceeded.
        """
        with self.client.post(
            "/api/v1/job-postings/ingest",
            json={"raw_text": "test", "source_url": "http://example.com"},
            catch_response=True,
        ) as response:
            if response.status_code in (200, 422, 429):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def chat_message(self) -> None:
        """POST /api/v1/chat/messages — rate limited at 10/minute.

        Sends a minimal body to trigger the rate limiter.
        """
        with self.client.post(
            "/api/v1/chat/messages",
            json={"message": "test"},
            catch_response=True,
        ) as response:
            if response.status_code in (200, 422, 429):
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
