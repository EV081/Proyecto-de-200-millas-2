# Cómo Mejorar el Rendimiento del Historial de Pedidos

## Problema Actual

La función `pedido_historial` usa un **Scan** con filtro para buscar pedidos por correo. Esto es ineficiente porque:
- Escanea toda la tabla item por item
- Consume muchas unidades de lectura (RCU)
- Tiene alta latencia cuando hay muchos pedidos
- No escala bien con el crecimiento de datos

## Solución: Crear un GSI (Global Secondary Index)

Un GSI permite hacer **Query** en lugar de **Scan**, lo cual es mucho más eficiente:
- Solo lee los items que coinciden con la clave
- Menor consumo de RCU
- Latencia baja y predecible
- Escala automáticamente

---

## Opción 1: Automático con setup_backend.sh (RECOMENDADO)

El GSI se crea automáticamente cuando ejecutas:

```bash
./setup_backend.sh
```

Y seleccionas la opción 1 (Desplegar todo) o la opción 3 (Solo infraestructura).

El script:
1. Crea la tabla de pedidos con el GSI incluido
2. Si la tabla ya existe, verifica si tiene el GSI
3. Si no tiene el GSI, lo crea automáticamente
4. Continúa con el resto del despliegue

**No necesitas hacer nada más**, el GSI se creará automáticamente.

---

## Opción 2: Crear el GSI con el Script Python (Manual)

Si ya desplegaste y quieres crear el GSI manualmente:

### Paso 1: Configurar variables de entorno

```bash
# Asegúrate de tener configurado el nombre de tu tabla
export TABLE_PEDIDOS="Millas-Pedidos"
```

### Paso 2: Ejecutar el script

```bash
python crear_gsi_pedidos.py
```

El script:
1. Verifica si el GSI ya existe
2. Si no existe, lo crea automáticamente
3. Espera a que esté activo (puede tomar varios minutos)
4. Confirma cuando está listo para usar

---

## Opción 3: Crear el GSI desde AWS Console

### Paso 1: Ir a DynamoDB Console
1. Abre AWS Console
2. Ve a DynamoDB > Tables
3. Selecciona tu tabla `Millas-Pedidos`

### Paso 2: Crear el índice
1. Ve a la pestaña **Indexes**
2. Click en **Create index**
3. Configura:
   - **Partition key:** `correo` (String)
   - **Sort key:** `created_at` (String)
   - **Index name:** `by_usuario_v2`
   - **Projected attributes:** All
4. Click **Create index**

### Paso 3: Esperar
- El índice tardará varios minutos en crearse
- El estado cambiará de "Creating" a "Active"
- Puedes usar la tabla mientras se crea el índice

---

## Opción 4: Crear el GSI con AWS CLI

```bash
aws dynamodb update-table \
    --table-name Millas-Pedidos \
    --attribute-definitions \
        AttributeName=correo,AttributeType=S \
        AttributeName=created_at,AttributeType=S \
    --global-secondary-index-updates \
        "[{\"Create\":{\"IndexName\":\"by_usuario_v2\",\"KeySchema\":[{\"AttributeName\":\"correo\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"created_at\",\"KeyType\":\"RANGE\"}],\"Projection\":{\"ProjectionType\":\"ALL\"},\"ProvisionedThroughput\":{\"ReadCapacityUnits\":5,\"WriteCapacityUnits\":5}}}]"
```

---

## Verificar que el GSI está Activo

### Con el script Python:
```bash
python crear_gsi_pedidos.py
```

### Con AWS CLI:
```bash
aws dynamodb describe-table --table-name Millas-Pedidos \
    --query 'Table.GlobalSecondaryIndexes[?IndexName==`by_usuario_v2`]'
```

Deberías ver:
```json
[
  {
    "IndexName": "by_usuario_v2",
    "IndexStatus": "ACTIVE",
    "KeySchema": [
      {
        "AttributeName": "correo",
        "KeyType": "HASH"
      },
      {
        "AttributeName": "created_at",
        "KeyType": "RANGE"
      }
    ]
  }
]
```

---

## Beneficios Después de Crear el GSI

### Antes (con Scan):
```
Tiempo de respuesta: 500-2000ms
RCU consumidas: 10-50 por request
Escalabilidad: Pobre
```

### Después (con Query + GSI):
```
Tiempo de respuesta: 50-200ms
RCU consumidas: 1-5 por request
Escalabilidad: Excelente
```

---

## Código Actualizado

El código de `pedido_historial.py` ya está preparado para:
1. **Intentar usar el GSI primero** (método eficiente)
2. **Usar Scan como fallback** si el GSI no existe (compatibilidad)

Esto significa que:
- ✓ Funciona ahora mismo (con Scan)
- ✓ Funcionará mejor automáticamente cuando crees el GSI
- ✓ No requiere cambios de código después de crear el GSI

---

## Notas Importantes

### Costos
- Crear un GSI es **gratis**
- El GSI consume almacenamiento adicional (duplica los datos indexados)
- Las queries al GSI consumen RCU como cualquier lectura

### Tiempo de Creación
- Tablas pequeñas (<1000 items): 1-5 minutos
- Tablas medianas (1000-10000 items): 5-15 minutos
- Tablas grandes (>10000 items): 15+ minutos

### Limitaciones
- Máximo 20 GSIs por tabla
- No puedes eliminar un GSI mientras se está creando
- Los datos existentes se indexarán automáticamente

---

## Recomendación

**El GSI se crea automáticamente** cuando ejecutas `./setup_backend.sh`. Si ya desplegaste antes de esta actualización, tienes dos opciones:

### Opción A: Re-desplegar (recomendado)
```bash
./setup_backend.sh
# Selecciona opción 3: Solo crear infraestructura y poblar datos
```

### Opción B: Crear solo el GSI
```bash
python crear_gsi_pedidos.py
```

Mientras tanto, la función seguirá funcionando con Scan, pero será más lenta.
