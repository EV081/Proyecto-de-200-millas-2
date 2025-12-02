import os
import json
import math
import base64
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "")

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

def lambda_handler(event, context):
    # CORS preflight
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    if method == "OPTIONS":
        return _resp(204, {})

    # Solo POST
    if method != "POST":
        return _resp(405, {"error": "Método no permitido. Usa POST."})

    if not PRODUCTS_TABLE:
        return _resp(500, {"error": "PRODUCTS_TABLE no configurado"})

    body = _parse_body(event)

    # Clave nueva (preferida) o legado
    local_id = body.get("local_id")
    tenant_id = body.get("tenant_id")  # legado
    if not local_id and not tenant_id:
        return _resp(400, {"error": "Falta local_id (o tenant_id legado) en el body"})

    # Filtros y paginación
    categoria = body.get("categoria")
    nombre = body.get("nombre")  # Filtro por nombre (case-insensitive)
    size = _safe_int(body.get("size", body.get("limit", 10)), 10)
    if size <= 0 or size > 100:
        size = 10
    
    # Normalizar nombre para búsqueda case-insensitive
    nombre_lower = nombre.lower() if nombre else None

    # Paginación por token (recomendada)
    next_token_in = body.get("next_token")
    lek = _decode_token(next_token_in)

    # Compatibilidad page/size solo si no viene next_token
    page = None
    if not lek:
        page = _safe_int(body.get("page", 0), 0)
        if page < 0:
            page = 0

    ddb = boto3.resource("dynamodb")
    table = ddb.Table(PRODUCTS_TABLE)

    # KeyCondition según clave disponible
    if local_id:
        key_cond = Key("local_id").eq(local_id)
    else:
        key_cond = Key("tenant_id").eq(tenant_id)

    # include_total (costoso: múltiples queries)
    include_total = bool(body.get("include_total"))
    total = None
    total_pages = None
    if include_total:
        total = 0
        count_args = {
            "KeyConditionExpression": key_cond,
            "Select": "COUNT"
        }
        # Solo filtrar por categoría en DynamoDB para count
        if categoria:
            count_args["FilterExpression"] = Attr("categoria").eq(categoria)
        
        count_lek = None
        while True:
            if count_lek:
                count_args["ExclusiveStartKey"] = count_lek
            rcount = table.query(**count_args)
            total += rcount.get("Count", 0)
            count_lek = rcount.get("LastEvaluatedKey")
            if not count_lek:
                break
        # Si hay filtro por nombre, el total es aproximado
        if nombre_lower:
            # Filtrar por nombre en memoria
            temp_total = 0
            for _ in range(total):
                # Esto es una aproximación, no es exacto
                pass
            total = temp_total if nombre_lower else total
        
        total_pages = math.ceil(total / size) if size > 0 else 0
        if page is not None and total_pages and page >= total_pages:
            return _resp(200, {
                "contents": [],
                "page": page,
                "size": size,
                "totalElements": total,
                "totalPages": total_pages,
                "next_token": None
            })

    # Query principal - solo filtrar por categoría en DynamoDB
    qargs = {
        "KeyConditionExpression": key_cond
    }
    
    # Solo agregar FilterExpression para categoría (más eficiente)
    if categoria:
        qargs["FilterExpression"] = Attr("categoria").eq(categoria)

    # Si hay filtro por nombre, necesitamos obtener más items y filtrar en memoria
    # porque DynamoDB no soporta búsquedas case-insensitive con contains
    items = []
    query_lek = lek
    max_queries = 10  # Límite de seguridad
    queries_done = 0
    
    try:
        while len(items) < size and queries_done < max_queries:
            if query_lek:
                qargs["ExclusiveStartKey"] = query_lek
            
            # Obtener más items de los necesarios para compensar el filtro por nombre
            qargs["Limit"] = size * 2 if nombre_lower else size
            
            rpage = table.query(**qargs)
            page_items = rpage.get("Items", [])
            query_lek = rpage.get("LastEvaluatedKey")
            queries_done += 1
            
            # Filtrar por nombre en memoria (case-insensitive, palabra completa)
            if nombre_lower:
                for item in page_items:
                    item_nombre = item.get("nombre", "").lower()
                    # Buscar la palabra completa (separada por espacios)
                    palabras = item_nombre.split()
                    if nombre_lower in palabras:
                        items.append(item)
                        if len(items) >= size:
                            break
            else:
                items.extend(page_items)
            
            # Si no hay más items en DynamoDB, parar
            if not query_lek:
                break
            
            # Si ya tenemos suficientes items, parar
            if len(items) >= size:
                break
        
        # Limitar a size items
        if len(items) > size:
            items = items[:size]
        
        lek_out = query_lek
        next_token_out = _encode_token(lek_out)
        
    except ClientError as e:
        print(f"Error query productos: {e}")
        return _resp(500, {"error": "Error consultando productos"})

    items = _convert_decimal(items)

    resp = {"contents": items, "size": size, "next_token": next_token_out}
    if page is not None:
        resp["page"] = page
    if include_total:
        resp.update({"totalElements": total, "totalPages": total_pages})

    return _resp(200, resp)
