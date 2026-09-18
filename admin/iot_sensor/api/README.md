# IoT API

The existing FastAPI application exposes:

- `GET /api/iot/hives`
- `POST /api/iot/hives/{hive_id}/readings`

Each POST inserts a new row into `public.hive_iot_data`.
