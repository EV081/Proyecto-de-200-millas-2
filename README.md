# 200 Millas – Auth (Register & Login) • README corto

Este README explica **solo** la parte de **usuarios**: *crear usuario* y *login*.
(La parte de productos e imágenes queda fuera.)

---

## Arquitectura mínima

* **API Gateway (HTTP API)**

  * `POST /usuarios/crear` → Lambda **CrearUsuario**
  * `POST /usuarios/login` → Lambda **LoginUsuario**
* **DynamoDB**

  * `t_usuarios` (PK `tenant_id`, SK `user_id`)
  * `t_tokens_acceso` (PK `token`)
* **Lambdas (Python 3.12)** con Serverless Framework v4.

---

## Variables de entorno (definidas en `serverless.yml`)

```yaml
USERS_TABLE=t_usuarios
TOKENS_TABLE=t_tokens_acceso
```

---

## Modelo de datos

### t_usuarios

```json
{
  "tenant_id": "6200millas",          // PK
  "user_id": "admin@6200millas.pe",   // SK (email)
  "password_hash": "sha256...",
  "role": "admin | customer",         // por defecto "customer"
  "created_at": "2025-11-08T12:34:56Z"
}
```

### t_tokens_acceso

```json
{
  "token": "uuid",                     // PK
  "tenant_id": "6200millas",
  "user_id": "admin@6200millas.pe",
  "role": "admin | customer",
  "expires": "YYYY-MM-DD HH:MM:SS"     // UTC
}
```

---

## Endpoints

### 1) Crear Usuario

* **POST** `/usuarios/crear`
* **Body (JSON)**:

```json
{
  "tenant_id": "6200millas",
  "user_id": "admin@6200millas.pe",
  "password": "Secreta123",
  "role": "admin"
}
```

* **Respuestas**:

  * `200` → `{"message":"Usuario registrado", "tenant_id":"...", "user_id":"...", "role":"admin"}`
  * `200` (si ya existe) → `{"message":"Usuario ya existe"}`
  * `400` → parámetros faltantes o `role` inválido
  * `500` → error interno

> Nota: Para MVP se permite enviar `role`. En producción, **no** permitir autoasignarse `admin`.

---

### 2) Login

* **POST** `/usuarios/login`
* **Body (JSON)**:

```json
{
  "tenant_id": "6200millas",
  "user_id": "admin@6200millas.pe",
  "password": "Secreta123"
}
```

* **Respuestas**:

  * `200` → `{"token":"<uuid>","expires":"<iso8601>","role":"admin"}`
  * `403` → credenciales inválidas
  * `400/500` → error de validación/servidor

El `token` se guarda en `t_tokens_acceso` y se usará para autorizar otros endpoints.

---

## Probar rápido

### Postman

1. **Crear usuario** con el JSON de arriba.
2. **Login** y guarda el `token`.

### cURL

```bash
# Crear usuario
curl -X POST "$BASE/usuarios/crear" \
 -H "Content-Type: application/json" \
 -d '{"tenant_id":"6200millas","user_id":"admin@6200millas.pe","password":"Secreta123","role":"admin"}'

# Login
curl -X POST "$BASE/usuarios/login" \
 -H "Content-Type: application/json" \
 -d '{"tenant_id":"6200millas","user_id":"admin@6200millas.pe","password":"Secreta123"}'
```

---

## Notas de implementación

* **Passwords**: se guardan con `sha256` (campo `password_hash`).
* **Expiración de tokens**: +60 min desde el login (UTC).
* **Multitenancy**: `tenant_id` agrupa a los usuarios por negocio.
* **Compatibilidad**: si un usuario antiguo no tiene `role`, `login` devuelve `"customer"` por defecto.

---
