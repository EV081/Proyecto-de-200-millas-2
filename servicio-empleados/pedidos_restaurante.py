import os
import json
import math
import base64
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

TABLE_PEDIDOS = os.environ.get("TABLE_PEDIDOS", "")

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

def _filter_productos(productos, categoria=None, nombre=None):
    """Filtra productos dentro de un pedido por categoría y/o nombre"""
    if not productos or not isinstance(productos, list):
        return []
    
    filtered = productos
    
    if categoria:
        filtered = [p for p in filtered if isinstance(p, dict) and p.get("categoria") == categoria]
    
    if nombre:
        nombre_lower = nombre.lower()
        filtered = [p for p in filtered if isinstance(p, dict) and nombre_lower in p.get("nombre", "").lower()]
    
    return filtered

def _matches_estado(pedido_estado, estado_filter):
    """Verifica si el estado del pedido coincide con el filtro"""
    if not estado_filter:
        return True
    return pedido_estado == estado_filter

def lambda_handler(event, context):
    # CORS preflight
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
    if method == "OPTIONS":
        return _resp(204, {})

    # Solo POST
    if method != "POST":
        return _resp(405, {"error": "Método no permitido. Usa POST."})

    if not TABLE_PEDIDOS:
        return _resp(500, {"error": "TABLE_PEDIDOS no configurado"})

    body = _parse_body(event)

    # Requerir local_id
    local_id = body.get("local_id")
    if not local_id:
        return _resp(400, {"error": "Falta local_id en el body"})

    # Filtros opcionales
    categoria = body.get("categoria")
    nombre = body.get("nombre")
    estado = body.get("estado")  # Filtro por estado
    
    # Paginación - si hay filtros, ignorar size y traer TODOS
    size = _safe_int(body.get("size", body.get("limit", 10)), 10)
    if size <= 0 or size > 1000:
        size = 10
    
    # Si hay filtros activos, traer TODOS los items que coincidan
    traer_todos = bool(estado or categoria or nombre)

    # Paginación por token (solo si NO hay filtros)
    next_token_in = body.get("next_token")
    lek = _decode_token(next_token_in) if not traer_todos else None

    ddb = boto3.resource("dynamodb")
    table = ddb.Table(TABLE_PEDIDOS)

    # Si hay filtros, obtener TODOS los items y filtrar en memoria
    filtered_items = []
    query_lek = lek
    queries_done = 0
    
    try:
        # Continuar consultando hasta obtener TODOS los items (si hay filtros) o hasta size (sin filtros)
        while True:
            qargs = {
                "KeyConditionExpression": Key("local_id").eq(local_id),
                "ScanIndexForward": False  # Más recientes primero
            }
            
            # Si NO hay filtros, usar paginación normal
            if not traer_todos:
                qargs["Limit"] = size
            
            if query_lek:
                qargs["ExclusiveStartKey"] = query_lek
            
            response = table.query(**qargs)
            page_items = response.get("Items", [])
            query_lek = response.get("LastEvaluatedKey")
            queries_done += 1
            
            # Aplicar filtros a los items de esta página
            for item in page_items:
                # Filtrar por estado si se especificó
                if estado and not _matches_estado(item.get("estado"), estado):
                    continue
                
                # Filtrar productos dentro del pedido si se especificaron filtros de producto
                if categoria or nombre:
                    productos = item.get("productos", [])
                    productos_filtrados = _filter_productos(productos, categoria, nombre)
                    
                    # Solo incluir el pedido si tiene productos que coinciden con los filtros
                    if productos_filtrados:
                        item_copy = item.copy()
                        item_copy["productos"] = productos_filtrados
                        filtered_items.append(item_copy)
                else:
                    # Sin filtros de producto, incluir el pedido completo
                    filtered_items.append(item)
                
                # Si NO hay filtros y ya tenemos suficientes, parar
                if not traer_todos and len(filtered_items) >= size:
                    break
            
            # Si no hay más items en DynamoDB, parar
            if not query_lek:
                break
            
            # Si NO hay filtros y ya tenemos suficientes items, parar
            if not traer_todos and len(filtered_items) >= size:
                break
        
        print(f"Query completado: {len(filtered_items)} pedidos encontrados después de {queries_done} query(s). Filtros activos: {traer_todos}")
        
    except ClientError as e:
        print(f"Error query pedidos: {e}")
        return _resp(500, {"error": "Error consultando pedidos del restaurante"})
    
    items = filtered_items
    # Si hay filtros, no hay next_token (se trajeron todos)
    lek_out = None if traer_todos else query_lek

    # Ordenar por fecha (created_at) descendente
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    next_token_out = _encode_token(lek_out)
    items = _convert_decimal(items)

    resp = {
        "pedidos": items,
        "size": size,
        "next_token": next_token_out,
        "local_id": local_id
    }

    return _resp(200, resp)
