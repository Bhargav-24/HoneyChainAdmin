# IoT backend integration

The IoT service implementation lives in `backend/app/services/iot_sensor.py` so it uses the existing FastAPI application and Supabase connection.

Creating a hive through `POST /api/hives` also inserts one randomized initial reading into `public.hive_iot_data`. Later readings are appended through the IoT reading endpoint.
