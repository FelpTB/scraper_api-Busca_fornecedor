web: hypercorn app.main:app --bind [::]:$PORT
discovery_worker: python -m app.workers.discovery_worker
worker: python -m app.workers.profile_worker
