# HTTP job management

The API now supports GET /api/downloads for queue status, POST /api/downloads/{job_id}/cancel for cancellation, and DELETE /api/downloads/{job_id} for removal of completed, failed, or cancelled jobs.

create_app accepts max_workers=2, max_queue=20, max_jobs=50 and retention_seconds=3600. Finished records and generated output files expire on later API requests. Cached chapter data remains intact.

Cancelling queued work is immediate when the worker has not started. Cancellation of running work is cooperative and takes effect at a progress callback or after the current blocking operation.

Jobs and queue are stored in memory and do not survive restarts. Keep the server bound to localhost unless protected by an authentication layer.
