import json
import os
import time
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sf = boto3.client("stepfunctions")
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]

def _parse_body(body: str):
    # JSON: {"id_pedido":"...", "estado":"..."}  ó  texto: "id_pedido,estado" (| : ; también)
    try:
        data = json.loads(body)
        if isinstance(data, dict) and "id_pedido" in data and "estado" in data:
            return str(data["id_pedido"]), str(data["estado"])
    except Exception:
        pass
    for sep in [",", "|", ":", ";"]:
        if sep in body:
            left, right = [s.strip() for s in body.split(sep, 1)]
            if left and right:
                return left, right
    raise ValueError("Body inválido. Usa JSON {'id_pedido','estado'} o 'id,estado'.")

def handler(event, context):
    logger.info("Evento SQS: %s", json.dumps(event))
    failures = []

    for record in event.get("Records", []):
        msg_id = record.get("messageId")
        body = record.get("body", "")

        try:
            id_pedido, estado = _parse_body(body)
            payload = {
                "id_pedido": id_pedido,
                "estado": estado,
                "source": "sqs.en_preparacion",
                "sqs_message_id": msg_id,
            }
            exec_name = f"{id_pedido}-{estado}-{int(time.time()*1000)}"[:80]
            resp = sf.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=exec_name,
                input=json.dumps(payload),
            )
            logger.info("StartExecution OK: %s", resp.get("executionArn"))
        except Exception as e:
            logger.exception("Fallo procesando %s: %s", msg_id, e)
            if msg_id:
                failures.append({"itemIdentifier": msg_id})

    # Partial batch response: solo reintenta los fallidos
    return {"batchItemFailures": failures}
