import os
import boto3
from botocore.exceptions import ClientError

TABLE_EMPLEADOS = os.environ.get("TABLE_EMPLEADOS", "")

dynamodb = boto3.resource("dynamodb")

def validar_empleado(local_id, dni):
    """
    Valida que un empleado existe en la tabla de empleados
    
    Args:
        local_id: ID del local/restaurante
        dni: DNI del empleado
        
    Returns:
        tuple: (es_valido: bool, empleado: dict|None, error: str|None)
    """
    if not TABLE_EMPLEADOS:
        return False, None, "TABLE_EMPLEADOS no configurado"
    
    if not local_id or not dni:
        return False, None, "local_id y dni son requeridos"
    
    try:
        table = dynamodb.Table(TABLE_EMPLEADOS)
        
        # La tabla tiene PK=local_id, SK=dni
        response = table.get_item(
            Key={
                "local_id": local_id,
                "dni": dni
            }
        )
        
        empleado = response.get("Item")
        
        if not empleado:
            return False, None, f"Empleado con DNI {dni} no encontrado en local {local_id}"
        
        # Verificar que el empleado esté activo (si existe ese campo)
        if empleado.get("activo") is False:
            return False, None, f"Empleado con DNI {dni} está inactivo"
        
        return True, empleado, None
        
    except ClientError as e:
        print(f"Error validando empleado: {e}")
        return False, None, f"Error consultando empleado: {str(e)}"
    except Exception as e:
        print(f"Error inesperado validando empleado: {e}")
        return False, None, f"Error inesperado: {str(e)}"
