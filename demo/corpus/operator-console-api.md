# Operator Console API

The Operator Console exposes a REST API on the Fleet Manager so that warehouse management systems can create jobs and read fleet status. All endpoints are under `https://<server>/api/v2` and require a bearer token created in the console's Integrations page.

## Jobs

`POST /api/v2/jobs` creates a transport job with a pickup location, a drop-off location, a priority from 1 to 5 and an optional deadline. The response contains the job id and its initial state, "queued". `GET /api/v2/jobs/{id}` returns the current state, which moves through queued, assigned, in_progress and done, or failed with a reason code. `DELETE /api/v2/jobs/{id}` cancels a job that has not started.

## Fleet status

`GET /api/v2/robots` lists every robot with its name, model, state of charge, current position and current job. `GET /api/v2/robots/{name}/events` returns the last 500 safety and maintenance events, which is useful for dashboards.

## Webhooks

Instead of polling, an integration can register a webhook URL under Integrations and receive a POST for every job state change and every safety event. Deliveries are retried for one hour with exponential backoff.

## Rate limits

Tokens are limited to 600 requests per minute. Exceeding the limit returns HTTP 429 with a Retry-After header. Job creation is additionally limited to 60 jobs per minute per token to protect the dispatcher.
