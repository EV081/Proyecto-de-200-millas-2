import json
from event_helper import publish_event, response
from empleado_helper import validar_empleado

def handler(event, context):
    """
    Trigger EnPreparacion event
    POST /empleados/cocina/iniciar
    Body: { "order_id": "...", "local_id": "...", "dni": "..." }
    """
    try:
        body = json.loads(event.get('body', '{}'))
        order_id = body.get('order_id')
        local_id = body.get('local_id')
        dni = body.get('dni')
        
        if not order_id or not local_id or not dni:
            return response(400, {
                'error': 'order_id, local_id y dni son requeridos'
            })
        
        # Validar que el empleado existe
        es_valido, empleado, error = validar_empleado(local_id, dni)
        
        if not es_valido:
            return response(403, {
                'error': f'Empleado no autorizado: {error}'
            })
        
        detail = {
            'order_id': order_id,
            'local_id': local_id,
            'empleado_dni': dni,
            'empleado_nombre': empleado.get('nombre', ''),
            'status': 'ACEPTADO'
        }
        
        success = publish_event('200millas.cocina', 'EnPreparacion', detail)
        
        if success:
            return response(200, {
                'message': 'EnPreparacion event published',
                'order_id': order_id,
                'empleado': empleado.get('nombre', dni)
            })
        else:
            return response(500, {
                'error': 'Failed to publish event'
            })
    
    except Exception as e:
        return response(500, {
            'error': str(e)
        })
