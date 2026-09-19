from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

PROJECT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_DIR / '.env')
load_dotenv()

router = APIRouter()

REQUESTS_DIR = Path(__file__).resolve().parent.parent.parent / 'requests'

SUPABASE_URL = os.getenv('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip() or os.getenv('SUPABASE_ANON_KEY', '').strip()
CERTIFICATE_BUCKET = os.getenv('SUPABASE_CERTIFICATE_BUCKET', 'honey-certificates')
LAB_RESULTS = {
    'quality_grade': 'A+',
    'moisture_percent': 17.4,
    'ph': 4.1,
    'hmf_mg_per_kg': 8.6,
    'adulteration_screen': 'Clear',
    'pollen_profile': 'Multifloral signature confirmed',
    'test_method': 'HoneyChain Collection Lab protocol',
}

try:
    from supabase import create_client

    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
    supabase_init_error = None
except Exception as error:
    supabase_client = None
    supabase_init_error = error


def require_supabase():
    if supabase_client is None:
        detail = 'Supabase client is unavailable.'
        if supabase_init_error:
            detail = f'Supabase client could not be initialized: {type(supabase_init_error).__name__}'
        raise HTTPException(status_code=503, detail=detail)
    return supabase_client

beekeepers = [
    {
        'beekeeper_id': 'demo-beekeeper-001',
        'name': 'Aster Honey Co.',
        'email': 'aster@example.com',
        'location': 'Napa Valley',
        'kyc_status': 'pending',
    },
    {
        'beekeeper_id': 'demo-beekeeper-002',
        'name': 'Sunrise Apiaries',
        'email': 'sunrise@example.com',
        'location': 'Bakersfield',
        'kyc_status': 'approved',
    },
]

batches = [
    {
        'batch_id': 'BATCH-1001',
        'hive_id': 'H-01',
        'honey_type': 'Wildflower',
        'harvest_date': '2026-09-15',
        'quantity': 120,
        'status': 'HARVESTED',
    },
    {
        'batch_id': 'BATCH-1002',
        'hive_id': 'H-02',
        'honey_type': 'Clover',
        'harvest_date': '2026-09-12',
        'quantity': 84,
        'status': 'PROCESSED',
    },
]

blockchain_events: list[dict[str, Any]] = []

iot_data: list[dict[str, Any]] = [
    {
        'id': 1,
        'hive_id': 'H-01',
        'recorded_at': '2026-09-17T10:00:00Z',
        'temperature': 23.4,
        'humidity': 62.1,
        'co2': 420.0,
        'weight': 120.5,
        'sound': 64.2,
        'bee_count': 4500,
    }
]

VALID_BATCH_TRANSITIONS = {
    'HARVESTED': 'PROCESSED',
    'PROCESSED': 'DISTRIBUTED',
}


def hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def batch_verification_payload(
    batch: dict[str, Any],
    hive: dict[str, Any],
    certificate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        'batch': {
            key: batch.get(key)
            for key in ('batch_id', 'hive_id', 'honey_type', 'harvest_date', 'quantity', 'status')
        },
        'hive': hive,
        'certificate': certificate or {},
    }


def batch_data_hash(batch: dict[str, Any], hive: dict[str, Any], certificate: dict[str, Any] | None = None) -> str:
    snapshot = batch_verification_payload(batch, hive, certificate)
    return hash_payload(snapshot)


def get_stored_certificate(batch_id: str) -> dict[str, Any] | None:
    if supabase_client is None:
        return None
    response = (
        supabase_client.table('batch_certificates')
        .select('*')
        .eq('batch_id', batch_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def issue_certificate(batch: dict[str, Any], hive: dict[str, Any]) -> dict[str, Any]:
    existing = get_stored_certificate(batch['batch_id'])
    if existing:
        return existing

    issued_at = datetime.now(timezone.utc).isoformat()
    certificate = {
        'certificate_id': f"HC-CERT-{batch['batch_id'].removeprefix('HB-')}",
        'batch_id': batch['batch_id'],
        'issued_at': issued_at,
        'lab_name': 'HoneyChain Collection Lab',
        'results': LAB_RESULTS,
    }
    beekeeper_name = 'Verified beekeeper'
    beekeeper_id = hive.get('beekeeper_id')
    if beekeeper_id:
        beekeeper_response = (
            supabase_client.table('beekeeper')
            .select('name')
            .eq('beekeeper_id', beekeeper_id)
            .limit(1)
            .execute()
        )
        if beekeeper_response.data:
            beekeeper_name = beekeeper_response.data[0].get('name') or beekeeper_name
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    pdf.setFillColor(colors.HexColor('#FCF6DA'))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor('#B5852B'))
    pdf.setLineWidth(0.7)
    pdf.rect(34, 30, width - 68, height - 60, fill=0, stroke=1)
    pdf.setLineWidth(0.45)
    pdf.rect(48, 44, width - 96, height - 88, fill=0, stroke=1)
    pdf.setFillColor(colors.HexColor('#8F6018'))
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawCentredString(width / 2, height - 63, 'HONEYCHAIN  /  COLLECTION CENTER')
    pdf.setFillColor(colors.HexColor('#302416'))
    pdf.setFont('Times-Bold', 28)
    pdf.drawCentredString(width / 2, height - 106, 'Certificate of Processed Honey')
    pdf.setFont('Helvetica', 10)
    pdf.setFillColor(colors.HexColor('#665030'))
    pdf.drawCentredString(width / 2, height - 130, 'This certificate confirms that the batch below passed the HoneyChain collection center release protocol.')
    pdf.setFillColor(colors.HexColor('#302416'))
    pdf.setFont('Helvetica-Bold', 15)
    pdf.drawCentredString(width / 2, height - 176, batch['batch_id'])
    pdf.setStrokeColor(colors.HexColor('#302416'))
    pdf.setLineWidth(0.8)
    pdf.line(145, height - 196, width - 145, height - 196)
    released_at = datetime.fromisoformat(issued_at).astimezone(timezone(timedelta(hours=5, minutes=30)))
    rows = [
        ('BEEKEEPER', beekeeper_name),
        ('HONEY PROFILE', batch.get('honey_type', 'Raw honey')),
        ('ORIGIN HIVE', batch['hive_id']),
        ('VOLUME', f"{batch.get('quantity', '-')} kg"),
        ('QUALITY GRADE', LAB_RESULTS['quality_grade']),
        ('RELEASED', released_at.strftime('%b %d, %Y, %I:%M %p')),
    ]
    pdf.setFont('Helvetica-Bold', 8)
    for index, (label, value) in enumerate(rows):
        x = 283 + (index % 2) * 275
        y = height - 250 - (index // 2) * 44
        pdf.setFillColor(colors.HexColor('#755626'))
        pdf.drawCentredString(x, y, label)
        pdf.setFillColor(colors.HexColor('#302416'))
        pdf.setFont('Helvetica-Bold', 9)
        pdf.drawCentredString(x, y - 14, str(value)[:42])
        pdf.setFont('Helvetica-Bold', 8)
    pdf.setFillColor(colors.HexColor('#8F6018'))
    pdf.setFont('Helvetica-Bold', 8)
    pdf.drawRightString(width - 58, 76, 'AUTHENTICITY RECORD')
    pdf.setFillColor(colors.HexColor('#665030'))
    pdf.setFont('Helvetica', 8)
    pdf.drawRightString(width - 58, 60, 'Issued by HoneyChain Collection Center  ·  Ledger linked')
    pdf.save()

    certificate_path = f"certificates/{batch['batch_id']}.pdf"
    try:
        supabase_client.storage.from_(CERTIFICATE_BUCKET).upload(
            certificate_path,
            pdf_buffer.getvalue(),
            {'content-type': 'application/pdf', 'upsert': 'true'},
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail='Certificate storage upload failed') from error

    certificate['storage_path'] = certificate_path
    response = supabase_client.table('batch_certificates').insert(certificate).execute()
    if not response.data:
        raise HTTPException(status_code=500, detail='Certificate record could not be created')
    return response.data[0]


def get_certificate_pdf(batch_id: str) -> bytes:
    certificate = get_stored_certificate(batch_id)
    if not certificate:
        raise HTTPException(status_code=404, detail='Certificate not issued for this batch')
    try:
        return supabase_client.storage.from_(CERTIFICATE_BUCKET).download(certificate['storage_path'])
    except Exception as error:
        raise HTTPException(status_code=502, detail='Stored certificate could not be fetched') from error


def append_blockchain_event(batch_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    previous_hash = None
    if supabase_client is not None:
        previous = (
            supabase_client.table('blockchain_blocks')
            .select('block_hash')
            .eq('batch_id', batch_id)
            .order('timestamp', desc=True)
            .limit(1)
            .execute()
        )
        previous_hash = previous.data[0]['block_hash'] if previous.data else None
    else:
        previous = next((item for item in reversed(blockchain_events) if item.get('batch_id') == batch_id), None)
        previous_hash = previous.get('block_hash') if previous else None
    event_timestamp = datetime.now(timezone.utc).isoformat()
    data_hash = hash_payload(payload)
    record = {
        'batch_id': batch_id,
        'event_type': event_type,
        'timestamp': event_timestamp,
        'data_hash': data_hash,
        'previous_hash': previous_hash,
        'block_hash': hash_payload({
            'batch_id': batch_id,
            'event_type': event_type,
            'data_hash': data_hash,
            'previous_hash': previous_hash,
            'timestamp': event_timestamp,
        }),
    }
    if supabase_client is not None:
        response = supabase_client.table('blockchain_blocks').insert({
            'batch_id': batch_id,
            'event_type': event_type,
            'timestamp': event_timestamp,
            'data_hash': data_hash,
            'previous_hash': previous_hash,
            'block_hash': record['block_hash'],
        }).execute()
        if not response.data:
            raise HTTPException(status_code=502, detail='Blockchain event could not be recorded')
    blockchain_events.append(record)
    return record


def fetch_db_rows(table_name: str, limit: int | None = None):
    client = require_supabase()
    try:
        query = client.table(table_name).select('*')
        if limit is not None:
            query = query.limit(limit)
        result = query.execute()
        return result.data or []
    except Exception as error:
        raise HTTPException(status_code=502, detail=f'Could not read {table_name} from Supabase.') from error


def update_db_row(table_name: str, key_name: str, key_value: str, payload: dict[str, Any]):
    if supabase_client is None:
        return None
    try:
        response = supabase_client.table(table_name).update(payload).eq(key_name, key_value).execute()
        if hasattr(response, 'data') and response.data:
            return response.data[0]
    except Exception:
        return None
    return None


class StatusUpdate(BaseModel):
    status: str = Field(..., min_length=1)


class IotReadingCreate(BaseModel):
    hive_id: str
    temperature: float | None = None
    humidity: float | None = None
    co2: float | None = None
    weight: float | None = None
    sound: float | None = None
    bee_count: int | None = None


class IotReadingUpdate(IotReadingCreate):
    pass


class IotReadingPayload(BaseModel):
    temperature: float | None = None
    humidity: float | None = None
    co2: float | None = None
    weight: float | None = None
    sound: float | None = None
    bee_count: int | None = None


@router.get('/')
def root():
    return FileResponse(REQUESTS_DIR.parent / 'home.html')


@router.get('/home')
def home():
    return FileResponse(REQUESTS_DIR.parent / 'home.html')


@router.get('/requests')
def serve_requests_page():
    return FileResponse(REQUESTS_DIR / 'requests.html')


@router.get('/iotdata')
def serve_iot_page():
    return FileResponse(Path(__file__).resolve().parent.parent.parent / 'iot_sensor' / 'frontend' / 'iot_sensor.html')


@router.get('/api/admin/requests')
def get_requests():
    return {
        'beekeepers': fetch_db_rows('beekeeper'),
        'batches': fetch_db_rows('honey_batches'),
        'blockchain_events': fetch_db_rows('blockchain_blocks'),
    }


@router.get('/api/public/batches/{batch_id}/certificate')
def get_public_certificate(batch_id: str):
    pdf_bytes = get_certificate_pdf(batch_id)
    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={'Content-Disposition': f'inline; filename="{batch_id}-honeychain-certificate.pdf"'},
    )


@router.patch('/api/admin/beekeepers/{beekeeper_id}')
def update_beekeeper_status(beekeeper_id: str, payload: StatusUpdate):
    if supabase_client is not None:
        updated = update_db_row('beekeeper', 'beekeeper_id', beekeeper_id, {'kyc_status': payload.status})
        if updated is not None:
            return updated
        raise HTTPException(status_code=404, detail='Beekeeper not found')

    for item in beekeepers:
        if item['beekeeper_id'] == beekeeper_id:
            item['kyc_status'] = payload.status
            return item
    raise HTTPException(status_code=404, detail='Beekeeper not found')


@router.patch('/api/admin/batches/{batch_id}')
def update_batch_status(batch_id: str, payload: StatusUpdate):
    if supabase_client is not None:
        current = supabase_client.table('honey_batches').select('*').eq('batch_id', batch_id).execute()
        if not getattr(current, 'data', None):
            raise HTTPException(status_code=404, detail='Batch not found')
        item = current.data[0]
        previous_status = str(item.get('status', '')).upper()
        next_status = VALID_BATCH_TRANSITIONS.get(previous_status)
        if next_status is None:
            raise HTTPException(status_code=400, detail='Batch status cannot be changed further.')
        next_status = next_status.upper()
        if payload.status.strip().upper() != next_status:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid transition. Expected {next_status} from {previous_status}.'
            )
        item['status'] = next_status
        hive_response = supabase_client.table('hives').select('*').eq('hive_id', item['hive_id']).limit(1).execute()
        if not hive_response.data:
            raise HTTPException(status_code=404, detail='Hive not found for batch')
        hive = hive_response.data[0]
        data_hash = batch_data_hash(item, hive)
        updated = supabase_client.table('honey_batches').update({'status': next_status}).eq('batch_id', batch_id).execute()
        if not updated.data:
            raise HTTPException(status_code=500, detail='Batch status could not be updated')
        try:
            event = append_blockchain_event(
                batch_id=batch_id,
                event_type=f'STATUS_{next_status}',
                payload=batch_verification_payload(item, hive),
            )
        except Exception as error:
            supabase_client.table('honey_batches').update({'status': previous_status}).eq('batch_id', batch_id).execute()
            if isinstance(error, HTTPException):
                raise
            raise HTTPException(status_code=502, detail='Batch status changed but blockchain event failed; update was rolled back') from error
        if event['data_hash'] != data_hash:
            supabase_client.table('honey_batches').update({'status': previous_status}).eq('batch_id', batch_id).execute()
            raise HTTPException(status_code=500, detail='Blockchain payload did not match the verification contract')
        certificate = None
        certificate_event = None
        if next_status == 'PROCESSED':
            certificate = issue_certificate(item, hive)
            certificate_event = append_blockchain_event(
                batch_id=batch_id,
                event_type='CERTIFICATE_ISSUED',
                payload=batch_verification_payload(item, hive, certificate),
            )
            if certificate_event['data_hash'] != batch_data_hash(item, hive, certificate):
                raise HTTPException(status_code=500, detail='Certificate event did not match the verification contract')
        return {
            'batch': item,
            'blockchain_event': event,
            'certificate': certificate,
            'certificate_event': certificate_event,
        }

    for item in batches:
        if item['batch_id'] == batch_id:
            previous_status = str(item['status']).upper()
            next_status = VALID_BATCH_TRANSITIONS.get(previous_status)
            if next_status is None:
                raise HTTPException(status_code=400, detail='Batch status cannot be changed further.')
            if payload.status.strip().upper() != next_status:
                raise HTTPException(
                    status_code=400,
                    detail=f'Invalid transition. Expected {next_status} from {previous_status}.'
                )
            item['status'] = next_status
            event = append_blockchain_event(
                batch_id=batch_id,
                event_type=f'STATUS_{payload.status}',
                payload={
                    'batch_id': batch_id,
                    'previous_status': previous_status,
                    'new_status': payload.status,
                    'hive_id': item['hive_id'],
                    'honey_type': item['honey_type'],
                    'quantity': item['quantity'],
                },
            )
            return {'batch': item, 'blockchain_event': event}
    raise HTTPException(status_code=404, detail='Batch not found')


@router.patch('/requests/{request_id}')
def update_request_status(request_id: str, payload: StatusUpdate):
    return update_beekeeper_status(request_id, payload)


@router.get('/api/hives')
def get_hives():
    if supabase_client is not None:
        rows = fetch_db_rows('hives')
        if rows:
            return rows
    return [
        {
            'hive_id': 'H-01',
            'location': 'North Orchard',
            'bee_species': 'Italian Honey Bee',
            'hive_type': 'Langstroth',
            'status': 'healthy',
        },
        {
            'hive_id': 'H-02',
            'location': 'South Meadow',
            'bee_species': 'Carniolan',
            'hive_type': 'Top Bar',
            'status': 'monitoring',
        },
    ]


@router.get('/api/iot/hives')
def get_iot_hives():
    return get_hives()


@router.get('/iotdata')
def list_iot_data():
    if supabase_client is not None:
        rows = fetch_db_rows('hive_iot_data')
        if rows:
            return rows
    return iot_data


@router.post('/iotdata')
def create_iot_data(record: IotReadingCreate):
    if supabase_client is not None:
        payload = {
            'hive_id': record.hive_id,
            'temperature': record.temperature,
            'humidity': record.humidity,
            'co2': record.co2,
            'weight': record.weight,
            'sound': record.sound,
            'bee_count': record.bee_count,
        }
        result = supabase_client.table('hive_iot_data').insert(payload).execute()
        if hasattr(result, 'data') and result.data:
            return result.data[0]
        raise HTTPException(status_code=500, detail='Could not create IoT record')

    new_id = max((item['id'] for item in iot_data), default=0) + 1
    new_record = {
        'id': new_id,
        'hive_id': record.hive_id,
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'temperature': record.temperature,
        'humidity': record.humidity,
        'co2': record.co2,
        'weight': record.weight,
        'sound': record.sound,
        'bee_count': record.bee_count,
    }
    iot_data.append(new_record)
    return new_record


@router.post('/api/iot/hives/{hive_id}/readings')
def create_iot_hive_reading(hive_id: str, record: IotReadingPayload):
    return create_iot_data(IotReadingCreate(hive_id=hive_id, **record.model_dump()))


@router.patch('/iotdata/{record_id}')
def update_iot_data(record_id: int, record: IotReadingUpdate):
    if supabase_client is not None:
        payload = {
            'hive_id': record.hive_id,
            'temperature': record.temperature,
            'humidity': record.humidity,
            'co2': record.co2,
            'weight': record.weight,
            'sound': record.sound,
            'bee_count': record.bee_count,
        }
        response = supabase_client.table('hive_iot_data').update(payload).eq('id', record_id).execute()
        if hasattr(response, 'data') and response.data:
            return response.data[0]
        raise HTTPException(status_code=404, detail='IoT reading not found')

    for item in iot_data:
        if item['id'] == record_id:
            item.update({
                'hive_id': record.hive_id,
                'temperature': record.temperature,
                'humidity': record.humidity,
                'co2': record.co2,
                'weight': record.weight,
                'sound': record.sound,
                'bee_count': record.bee_count,
                'recorded_at': datetime.now(timezone.utc).isoformat(),
            })
            return item
    raise HTTPException(status_code=404, detail='IoT reading not found')
