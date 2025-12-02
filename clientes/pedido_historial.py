import os
import json
import math
import base64
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from auth_helper import get_bearer_token, validate_token_via_lambda

TABLE_PEDIDOS = os.environ["TABLE_PEDIDOS"]
TOKENS_TABLE_USERS = os.environ["TOKENS_TABLE_USERS"]

dynamodb = boto3.resource("dynamodb")
pedidos_table = dynamodb.Table(TABLE_PEDIDOS)
tokens_table = dynamodb.Table(TOKENS_TABLE_USERS)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST"
}

def _resp(code, body):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json", **CORS_HEADERS},
        "body": json.dumps(body, ensure_ascii=False, default=str)
    }

def _parse_body(event):
    body = event.get("body")
    if isinstance(body, str):
        return json.loads(body) if body.strip() else {}
    return body if isinstance(body, dict) else {}

def _safe_int(v, default):
    try:
        return int(v)
    except Exception:
        return default

def _convert_decimal(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _convert_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_decimal(i) for i in obj]
    return obj

def _encode_token(lek: dict | None) -> str | None:
    if not lek:
        return None
    return base64.urlsafe_b64encode(json.dumps(lek).encode("utf-8")).decode("ascii")

def _decode_token(tok: str | None) -> dict | None:
    if not tok:
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(tok.encode("ascii")).decode("utf-8"))
    except Exception:
        return None

def _get_correo_from_token(token: str):
    """Obtiene el correo del usuario desde el token en la tabla"""
    try:
        r = tokens_table.get_item(Key={"token": token})
        item = r.get("Item")
        if not item:
            return None
        return item.get("correo") or item.get("email") or item.get("usuario_correo") or item.get("user_id")
    except Exception:
        return None

def lambda_handler(event, context):
    # CORS preflight
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    if method == "OPTIONS":
        return _resp(204, {})

    # Solo POST
    if method != "POST":
        return _resp(405, {"error": "Método no permitido. Usa POST."})

    # Validar token mediante Lambda
    token = get_bearer_token(event)
    valido, error, rol = validate_token_via_lambda(token)
    if not valido:
        return _resp(403, {"status": "Forbidden - Acceso No Autorizado", "error": error})
    
    # Obtener correo del token
    correo_token = _get_correo_from_token(token)
    if not correo_token:
        return _resp(403, {"error": "Token sin correo asociado"})
    
    # Verificar que sea Cliente
    if rol.lower() != "cliente":
        return _resp(403, {"error": "Permiso denegado: se requiere rol 'cliente'"})

    body = _parse_body(event)

    # Paginación
    size = _safe_int(body.get("size", body.get("limit", 10)), 10)
    if size <= 0 or size > 100:
        size = 10

    # Paginación por token
    next_token_in = body.get("next_token")
    lek = _decode_token(next_token_in)

    # Query usando GSI by_usuario_v2 (correo como PK, created_at como SK)
    qargs = {
        "IndexName": "by_usuario_v2",
        "KeyConditionExpression": Key("correo").eq(correo_token),
        "Limit": size,
        "ScanIndexForward": False  # Ordenar por created_at descendente (más reciente primero)
    }

    if lek:
        qargs["ExclusiveStartKey"] = lek

    try:
        response = pedidos_table.query(**qargs)
    except ClientError as e:
        print(f"Error query pedidos: {e}")
        return _resp(500, {"error": "Error consultando historial de pedidos"})

    items = response.get("Items", [])
    lek_out = response.get("LastEvaluatedKey")
    next_token_out = _encode_token(lek_out)

    items = _convert_decimal(items)

    resp = {
        "pedidos": items,
        "size": size,
        "next_token": next_token_out
    }

    return _resp(200, resp)
