# API Admin Línea (ADMIN_LINEA)

Panel web y app Flutter comparten el mismo contrato JSON. Base URL dev: `http://localhost:3000`.

**Usuario de prueba:** `admin-linea@example.com` / `<contraseña>`  
**Rol:** `ADMIN_LINEA` (id `ADMIN_LINEA`, route `admin/home`)

**Auth header:** `Authorization: Bearer <token>`  
El login devuelve el token ya prefijado: `"token": "Bearer eyJ..."`. Enviar ese valor tal cual en el header.

---

## Auth

### POST `/auth/login`

| | |
|---|---|
| **Body** | `{ "email": "...", "password": "..." }` |
| **200** | `{ "token": "Bearer ...", "user": { "id", "name", "lastname", "email", "phone", "image", "notification_token", "roles": [{ "id", "name", "route", "image" }] } }` |
| **400** | `{ "message": "...", "statusCode": 400 }` — email/password faltantes |
| **401** | `{ "message": "El email o la contraseña no son válidos", "statusCode": 401 }` |
| **403** | `{ "message": "Usuario inactivo", "statusCode": 403 }` |

---

## Admin línea (`/admin-linea/*`)

Todos requieren JWT y rol **ADMIN_LINEA**. Solo gestiona conductores de **su línea** (`user.line_id`).

Errores comunes en todos los endpoints:

| Código | Cuándo |
|--------|--------|
| **401** | Sin token, token inválido o usuario no encontrado |
| **403** | Usuario sin rol ADMIN_LINEA, admin inactivo, o conductor de otra línea |
| **400** | `{ "message": "..." }` — validación de negocio |

### Shape de conductor (lista e item)

```json
{
  "id": 1,
  "name": "...",
  "lastname": "...",
  "email": "...",
  "phone": "...",
  "image": "http://localhost:3000/media/...",
  "is_active": true,
  "line": { "id": 1, "name": "San Benito" },
  "roles": [{ "id": "DRIVER", "name": "...", "route": "...", "image": "..." }],
  "created_at": "...",
  "updated_at": "...",
  "deactivated_at": null,
  "deactivated_by": null,
  "created_by_admin_linea": { "id", "name", "lastname", "email" }
}
```

> `password` **nunca** se incluye en responses.

---

### GET `/admin-linea/drivers`

| | |
|---|---|
| **Query** | `is_active` opcional: `true` (default) \| `false` |
| **200** | JSON **array** de conductores (activos por defecto; `?is_active=false` → inactivos de la línea) |
| **400** | `{ "message": "is_active debe ser true o false" }` |

---

### POST `/admin-linea/drivers`

| | |
|---|---|
| **Body** | `{ "name", "lastname", "email", "phone", "password", "image" (opcional, URL o null) }` |
| **201** | Objeto conductor creado (mismo shape que arriba) |
| **400** | Campos obligatorios faltantes, email/teléfono duplicado |
| **500** | Rol DRIVER no existe en BD |

---

### PATCH `/admin-linea/drivers/{id}/deactivate`

| | |
|---|---|
| **Body** | `{}` |
| **200** | `{ "success": true, "driver": { ...conductor con is_active: false } }` |
| **404** | `{ "message": "Conductor no encontrado" }` |
| **403** | Conductor de otra línea |

Desactivación lógica: `is_active=false`, conserva registro e historial.

---

### DELETE `/admin-linea/drivers/{id}`

Solo si el conductor está **inactivo** (`is_active=false`).

| | |
|---|---|
| **200** | `{ "success": true, "message": "Conductor eliminado definitivamente de la línea", "driver_id": N }` |
| **400** | `{ "message": "Primero debes desactivar el conductor antes de eliminarlo definitivamente" }` |
| **404** | Conductor no encontrado |
| **403** | Otra línea |

No borra el usuario de BD (preserva viajes). Quita rol DRIVER, posición, bike info y `line`.

**Flujo UI recomendado:** Activos → desactivar → Inactivos (`?is_active=false`) → eliminar definitivamente.

---

### PATCH `/admin-linea/profile`

| | |
|---|---|
| **Body** | `{ "name", "lastname", "phone", "image" (opcional URL), "password" (opcional, web) }` — al menos un campo |
| **200** | Objeto admin actualizado (mismo shape conductor, sin password) |
| **400** | Sin campos, teléfono duplicado, password vacío |

---

### PUT/POST `/admin-linea/drivers/{id}/upload` *(web)*

Subida multipart de foto de conductor por el admin (misma línea).

| | |
|---|---|
| **Content-Type** | `multipart/form-data` |
| **Campo** | `file` (archivo imagen) |
| **200** | Objeto conductor con `image` URL absoluta |
| **400** | `{ "message": "file es obligatorio (multipart/form-data)" }` |
| **404/403** | Igual que otros endpoints de conductor |

**Alternativa existente (solo el propio usuario):** `PUT /users/upload/{id_user}` con campo `file` — el admin **no** puede usarlo para subir foto de un conductor ajeno (403).

**Flujo web recomendado:**

1. `POST /admin-linea/drivers` (sin imagen o con URL externa)
2. `PUT /admin-linea/drivers/{id}/upload` con `FormData` + `file`

Para foto del **admin**: `PATCH /admin-linea/profile` con URL, o `PUT /users/upload/{admin_id}` como ese usuario.

---

## Panel empresarial (control administrativo web)

Cada admin gestiona **solo su línea** (no hay multi-línea en un mismo usuario ADMIN_LINEA).

### GET `/admin-linea/line`

Info de la línea del admin + tarifas vigentes.

### GET `/admin-linea/dashboard` o `/admin-linea/reports/summary`

Resumen operativo:

```json
{
  "line": { "id", "name" },
  "drivers": { "active", "inactive", "with_live_position" },
  "trips": { "total", "finished", "cancelled", "active", "created_open" },
  "revenue": { "total_finished_usd", "today_finished_usd", "currency": "USD" },
  "generated_at": "..."
}
```

### GET `/admin-linea/trips`

| Query | Descripción |
|-------|-------------|
| `status` | `CREATED`, `ACCEPTED`, `ON_THE_WAY`, `ARRIVED`, `TRAVELLING`, `FINISHED`, `CANCELLED` |
| `from` / `to` | Rango de fechas ISO (`YYYY-MM-DD`) |
| `limit` / `offset` | Paginación (default 50, max 200) |

**200:** `{ "count", "limit", "offset", "results": [ viaje... ] }`

Viajes incluidos si el conductor asignado está en la línea, fue creado por el admin, o un conductor de la línea hizo oferta.

### GET `/admin-linea/trips/{id}`

Detalle del viaje + `offers[]` de conductores de la línea.

### GET `/admin-linea/trips/export`

Descarga CSV con los mismos filtros que `/trips` (`status`, `from`, `to`).

### GET `/admin-linea/drivers/positions`

Mapa en vivo: array `[{ "id_driver", "lat", "lng", "name", "lastname", "phone", "image", "is_active" }]`.

Posiciones desde `drivers_position` (actualizadas vía app móvil `POST /drivers-position`).

### GET `/admin-linea/clients`

Clientes que han tenido viajes con conductores de la línea.

**200:** `{ "count", "limit", "offset", "results": [{ "id", "name", ..., "trip_count", "finished_trip_count", "last_trip_at" }] }`

Solo lectura (no hay CRUD de clientes por línea).

### GET / PATCH `/admin-linea/fares`

Tarifas por línea (`km_value`, `min_value`, `min_fare_usd` fijo 0.80).

- **GET:** si no hay tarifa propia de la línea, devuelve fallback global con `"uses_global_fallback": true`.
- **PATCH body:** `{ "km_value", "min_value" }` — crea o actualiza tarifa de la línea.

> La app móvil de cotización (`GET /client-requests/.../.../.../...`) sigue usando tarifa global id=1 por ahora; la tarifa por línea es configurable desde el panel.

### GET `/admin-linea/drivers/{id}`

Detalle de un conductor (incluye auditoría).

### PATCH `/admin-linea/drivers/{id}`

Editar conductor: `{ "name", "lastname", "email", "phone", "image", "password" }` (al menos un campo).

### PATCH `/admin-linea/drivers/{id}/reactivate`

Reactiva conductor inactivo de la línea (`is_active=true`, limpia `deactivated_at` / `deactivated_by`).

**200:** `{ "success": true, "driver": { ... } }`

---

## CORS (SPA web)

Orígenes permitidos en dev:

- `http://localhost:5173`
- `http://127.0.0.1:5173`
- `http://localhost:3001`

Headers: `Authorization`, `Content-Type` (+ estándares del navegador)  
Métodos: `GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS`, `PUT`

---

## Ejemplo curl

```bash
# Login
curl -s -X POST http://localhost:3000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin-linea@example.com","password":"<contraseña>"}'

# Listar conductores activos (copiar token del login)
curl -s http://localhost:3000/admin-linea/drivers \
  -H "Authorization: Bearer eyJ..."

# Listar inactivos
curl -s "http://localhost:3000/admin-linea/drivers?is_active=false" \
  -H "Authorization: Bearer eyJ..."
```

---

## Compatibilidad Flutter

- Listas como **JSON array** directo (sin wrapper `{ data: [] }`).
- Campos **snake_case**: `is_active`, `lastname`, etc.
- Token login incluye prefijo `Bearer `; el cliente puede enviarlo tal cual.
- Respuestas deactivate/delete incluyen campos extra (`success`, `driver`) — no rompen parsers que ignoren claves desconocidas.

---

## Verificación rápida (criterios de aceptación)

| Check | Resultado esperado |
|-------|-------------------|
| Login `admin-linea@example.com` | 200 + token + rol ADMIN_LINEA |
| GET `/admin-linea/drivers` | 200 + array |
| POST crear conductor | 201 |
| PATCH deactivate | 200 + `is_active: false` |
| DELETE sin desactivar | 400 |
| DELETE tras desactivar | 200 |
| OPTIONS desde `localhost:5173` | 200 + headers CORS |
| Usuario sin ADMIN_LINEA | 403 |
