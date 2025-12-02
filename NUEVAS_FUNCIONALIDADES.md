# Nuevas Funcionalidades - API 200 Millas

## 1. Filtro por Nombre en Listado de Productos

**Endpoint:** `POST /productos/list`

**Descripción:** Ahora acepta un filtro adicional por nombre de producto (búsqueda parcial).

**Body de ejemplo:**
```json
{
  "local_id": "local-123",
  "categoria": "platos",
  "nombre": "ceviche",
  "size": 10,
  "next_token": null
}
```

**Parámetros:**
- `local_id` (requerido): ID del local/restaurante
- `categoria` (opcional): Filtrar por categoría
- `nombre` (opcional): Filtrar por nombre (búsqueda parcial, case-insensitive)
- `size` (opcional): Cantidad de resultados por página (default: 10, max: 100)
- `next_token` (opcional): Token para paginación

**Respuesta:**
```json
{
  "contents": [
    {
      "local_id": "local-123",
      "producto_id": "prod-456",
      "nombre": "Ceviche de Pescado",
      "categoria": "platos",
      "precio": 25.50,
      "descripcion": "Ceviche fresco del día"
    }
  ],
  "size": 10,
  "next_token": "eyJsb2NhbF9pZCI6ImxvY2FsLTEyMyIsInByb2R1Y3RvX2lkIjoicHJvZC00NTYifQ=="
}
```

---

## 2. Historial de Pedidos para Usuarios

**Endpoint:** `POST /pedido/historial`

**Descripción:** Permite a los clientes ver su historial completo de pedidos con paginación.

**Headers:**
```
Authorization: Bearer <token_del_cliente>
```

**Body de ejemplo:**
```json
{
  "size": 20,
  "next_token": null
}
```

**Parámetros:**
- `size` (opcional): Cantidad de pedidos por página (default: 10, max: 100)
- `next_token` (opcional): Token para paginación

**Respuesta:**
```json
{
  "pedidos": [
    {
      "local_id": "local-123",
      "pedido_id": "abc-123-def",
      "correo": "cliente@example.com",
      "productos": [
        {
          "producto_id": "prod-456",
          "nombre": "Ceviche",
          "cantidad": 2,
          "categoria": "platos"
        }
      ],
      "costo": 51.00,
      "direccion": "Av. Principal 123",
      "estado": "entregado",
      "created_at": "2024-12-01T10:30:00Z"
    }
  ],
  "size": 20,
  "next_token": "eyJsb2NhbF9pZCI6ImxvY2FsLTEyMyIsInBlZGlkb19pZCI6ImFiYy0xMjMtZGVmIn0="
}
```

**Notas:**
- Requiere autenticación con rol "cliente"
- Los pedidos se ordenan del más reciente al más antiguo
- Solo muestra los pedidos del usuario autenticado

---

## 3. Lista de Pedidos por Restaurante (Empleados)

**Endpoint:** `POST /empleados/pedidos/restaurante`

**Descripción:** Permite a los empleados ver todos los pedidos de un restaurante con filtros por categoría y nombre de producto.

**Body de ejemplo:**
```json
{
  "local_id": "local-123",
  "categoria": "bebidas",
  "nombre": "combo",
  "size": 15,
  "next_token": null
}
```

**Parámetros:**
- `local_id` (requerido): ID del restaurante
- `categoria` (opcional): Filtrar pedidos que contengan productos de esta categoría
- `nombre` (opcional): Filtrar pedidos que contengan productos con este nombre (búsqueda parcial)
- `size` (opcional): Cantidad de pedidos por página (default: 10, max: 100)
- `next_token` (opcional): Token para paginación

**Respuesta:**
```json
{
  "pedidos": [
    {
      "local_id": "local-123",
      "pedido_id": "xyz-789-abc",
      "correo": "cliente@example.com",
      "productos": [
        {
          "producto_id": "prod-789",
          "nombre": "Combo Familiar",
          "cantidad": 1,
          "categoria": "combos"
        }
      ],
      "costo": 85.00,
      "direccion": "Calle Secundaria 456",
      "estado": "en_preparacion",
      "created_at": "2024-12-02T14:20:00Z"
    }
  ],
  "size": 15,
  "next_token": "eyJsb2NhbF9pZCI6ImxvY2FsLTEyMyIsInBlZGlkb19pZCI6Inh5ei03ODktYWJjIn0=",
  "local_id": "local-123"
}
```

**Notas:**
- Los pedidos se ordenan del más reciente al más antiguo
- Si se especifican filtros de categoría o nombre, solo se muestran los pedidos que contengan productos que coincidan
- Los productos dentro de cada pedido se filtran según los criterios especificados
- Útil para que la cocina vea solo pedidos con ciertos tipos de productos

---

## Paginación

Todas las funciones usan paginación basada en tokens:

1. **Primera petición:** No envíes `next_token`
2. **Siguientes peticiones:** Usa el `next_token` de la respuesta anterior
3. **Última página:** Cuando `next_token` es `null`, no hay más resultados

**Ejemplo de flujo:**
```javascript
// Primera página
let response = await fetch('/productos/list', {
  method: 'POST',
  body: JSON.stringify({ local_id: 'local-123', size: 10 })
});
let data = await response.json();

// Segunda página
if (data.next_token) {
  response = await fetch('/productos/list', {
    method: 'POST',
    body: JSON.stringify({ 
      local_id: 'local-123', 
      size: 10,
      next_token: data.next_token 
    })
  });
}
```
