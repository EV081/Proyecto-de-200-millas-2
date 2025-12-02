#!/usr/bin/env python3
"""
Script para crear el GSI by_usuario_v2 en la tabla de pedidos.
Este índice permite buscar pedidos por correo de forma eficiente.

Uso:
    python crear_gsi_pedidos.py

Requisitos:
    - AWS CLI configurado con credenciales
    - Variable de entorno TABLE_PEDIDOS o editar el nombre de la tabla abajo
"""

import os
import boto3
import time

# Nombre de la tabla (ajusta según tu .env)
TABLE_NAME = os.environ.get("TABLE_PEDIDOS", "Millas-Pedidos")

def create_gsi():
    """Crea el GSI by_usuario_v2 en la tabla de pedidos"""
    dynamodb = boto3.client('dynamodb')
    
    print(f"Creando GSI 'by_usuario_v2' en la tabla '{TABLE_NAME}'...")
    
    try:
        response = dynamodb.update_table(
            TableName=TABLE_NAME,
            AttributeDefinitions=[
                {
                    'AttributeName': 'correo',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'created_at',
                    'AttributeType': 'S'
                }
            ],
            GlobalSecondaryIndexUpdates=[
                {
                    'Create': {
                        'IndexName': 'by_usuario_v2',
                        'KeySchema': [
                            {
                                'AttributeName': 'correo',
                                'KeyType': 'HASH'  # Partition key
                            },
                            {
                                'AttributeName': 'created_at',
                                'KeyType': 'RANGE'  # Sort key
                            }
                        ],
                        'Projection': {
                            'ProjectionType': 'ALL'  # Incluye todos los atributos
                        },
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                }
            ]
        )
        
        print("✓ Solicitud de creación enviada exitosamente")
        print(f"  Estado de la tabla: {response['TableDescription']['TableStatus']}")
        print("\nEsperando a que el índice se cree...")
        print("Esto puede tomar varios minutos dependiendo del tamaño de la tabla.")
        
        # Esperar a que el índice esté activo
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=TABLE_NAME)
        
        # Verificar el estado del GSI
        while True:
            table_info = dynamodb.describe_table(TableName=TABLE_NAME)
            gsi_status = None
            
            if 'GlobalSecondaryIndexes' in table_info['Table']:
                for gsi in table_info['Table']['GlobalSecondaryIndexes']:
                    if gsi['IndexName'] == 'by_usuario_v2':
                        gsi_status = gsi['IndexStatus']
                        break
            
            if gsi_status == 'ACTIVE':
                print("\n✓ ¡GSI 'by_usuario_v2' creado exitosamente!")
                print("\nAhora puedes usar queries eficientes por correo:")
                print("  - Partition Key: correo")
                print("  - Sort Key: created_at")
                break
            elif gsi_status == 'CREATING':
                print(".", end="", flush=True)
                time.sleep(10)
            else:
                print(f"\n⚠ Estado inesperado del GSI: {gsi_status}")
                break
                
    except dynamodb.exceptions.ResourceInUseException:
        print("⚠ La tabla está siendo actualizada. Espera un momento e intenta de nuevo.")
    except dynamodb.exceptions.LimitExceededException:
        print("⚠ Has alcanzado el límite de GSIs para esta tabla (máximo 20).")
    except Exception as e:
        print(f"✗ Error al crear el GSI: {e}")
        return False
    
    return True

def verify_gsi():
    """Verifica que el GSI existe y está activo"""
    dynamodb = boto3.client('dynamodb')
    
    try:
        response = dynamodb.describe_table(TableName=TABLE_NAME)
        
        if 'GlobalSecondaryIndexes' not in response['Table']:
            print(f"La tabla '{TABLE_NAME}' no tiene GSIs.")
            return False
        
        for gsi in response['Table']['GlobalSecondaryIndexes']:
            if gsi['IndexName'] == 'by_usuario_v2':
                print(f"\n✓ GSI 'by_usuario_v2' encontrado:")
                print(f"  Estado: {gsi['IndexStatus']}")
                print(f"  Partition Key: {gsi['KeySchema'][0]['AttributeName']}")
                print(f"  Sort Key: {gsi['KeySchema'][1]['AttributeName']}")
                return gsi['IndexStatus'] == 'ACTIVE'
        
        print(f"GSI 'by_usuario_v2' no encontrado en la tabla '{TABLE_NAME}'.")
        return False
        
    except Exception as e:
        print(f"Error al verificar el GSI: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Creador de GSI para Tabla de Pedidos")
    print("=" * 60)
    print()
    
    # Verificar si ya existe
    if verify_gsi():
        print("\n✓ El GSI ya existe y está activo. No es necesario crearlo.")
    else:
        print("\nEl GSI no existe. Procediendo a crearlo...\n")
        if create_gsi():
            print("\n" + "=" * 60)
            print("Proceso completado exitosamente")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("El proceso falló. Revisa los errores arriba.")
            print("=" * 60)
