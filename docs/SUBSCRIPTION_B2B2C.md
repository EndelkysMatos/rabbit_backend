# Suscripción B2B2C por línea (Rabbit)

Modelo de negocio: cada **línea de mototaxi** paga suscripción mensual a Rabbit. Los viajes entre cliente y conductor se cobran **fuera de la plataforma** (efectivo/transferencia). **No hay pasarela de pago** integrada.

## Planes y estados

| plan | Límite conductores | Cobro |
|------|-------------------|-------|
| `piloto` | 15 activos | Gratis hasta `pilot_ends_at` (90 días al alta) |
| `basico` | Ilimitado | Mensual manual |
| `pro` | Ilimitado | Mensual manual (features futuras) |

| status | Efecto |
|--------|--------|
| `activa` | Operación normal |
| `morosa` | Panel accesible; aviso; job puede escalar a suspendida |
| `suspendida` | No crear conductores; conductores no reciben viajes nuevos |

Enums JSON **exactos** (minúsculas, sin tildes): `piloto|basico|pro`, `activa|morosa|suspendida`.

## Alta de línea nueva

Al crear un registro `Line`, signal `ensure_line_subscription` crea:

- `plan=piloto`, `status=activa`
- `started_at=now`
- `pilot_ends_at=now + 90 días`

## Cobro manual (operador Rabbit)

1. Cliente de línea paga por transferencia/factura fuera del sistema.
2. Super-admin Rabbit registra pago:

```http
POST /admin/super/lines/{id}/subscription/record-payment
Authorization: Bearer <token RABBIT_SUPER>
Content-Type: application/json

{
  "plan": "basico",
  "last_payment_at": "2026-04-02T10:00:00Z",
  "notes": "Pagó abril — transferencia Banco X"
}
```

3. O actualización manual:

```http
PATCH /admin/super/lines/{id}/subscription
{
  "plan": "basico",
  "status": "activa",
  "next_billing_at": "2026-05-01T00:00:00Z",
  "last_payment_at": "2026-04-02T10:00:00Z",
  "notes": "..."
}
```

Endpoints super-admin adicionales:

- `POST .../subscription/activate`
- `POST .../subscription/suspend`

Requiere rol JWT **`RABBIT_SUPER`** (asignar en `user_has_roles`).

## Job diario

```bash
python manage.py process_line_subscriptions
```

Reglas automáticas (configurables en `settings.py`):

| Setting | Default | Uso |
|---------|---------|-----|
| `SUBSCRIPTION_PILOT_DAYS` | 90 | Duración piloto |
| `SUBSCRIPTION_PILOT_MAX_DRIVERS` | 15 | Límite piloto |
| `SUBSCRIPTION_GRACE_DAYS` | 7 | Gracia tras `next_billing_at` antes de morosa (básico/pro) |
| `SUBSCRIPTION_MOROSA_TO_SUSPEND_DAYS` | 15 | Días en morosa antes de suspendida automática |

Transiciones:

1. Piloto vencido sin pago → `morosa` (`next_billing_at = pilot_ends_at`)
2. Básico/pro: `next_billing_at + gracia` sin pago → `morosa`
3. Morosa ≥ 15 días → `suspendida`

## API ADMIN_LINEA (lectura)

`GET /admin-linea/dashboard` y `GET /admin-linea/line` incluyen:

```json
"line": {
  "id": 1,
  "name": "San Benito",
  "subscription": {
    "plan": "piloto",
    "status": "activa",
    "started_at": "...",
    "pilot_ends_at": "...",
    "next_billing_at": null,
    "last_payment_at": null,
    "days_until_pilot_end": 45,
    "max_drivers": 15,
    "active_drivers_count": 8
  }
}
```

`GET /admin-linea/subscription` → solo el objeto `subscription`.

Dashboard **siempre 200** aunque la línea esté suspendida (para mostrar aviso en admin-web).

## Validaciones

| Condición | Endpoint | Respuesta |
|-----------|----------|-----------|
| Línea suspendida | `POST /admin-linea/drivers` | 403 `Línea suspendida. Contacte a Rabbit.` |
| Piloto ≥ 15 conductores | `POST /admin-linea/drivers` | 403 `Límite del plan Piloto (15 conductores)` |
| Línea suspendida | `GET /client-requests/{lat}/{lng}` (conductor) | 200 `[]` |
| Línea suspendida | `POST /driver-trip-offers` | 403 |
| Línea suspendida | `PUT /client-requests/updateDriverAssigned` | 403 |

## Decisiones documentadas (equipo)

1. **Gracia post-factura:** 7 días (`SUBSCRIPTION_GRACE_DAYS`).
2. **Morosa → suspendida:** 15 días (`SUBSCRIPTION_MOROSA_TO_SUSPEND_DAYS`) o suspensión manual Rabbit.
3. **Viajes en curso al suspender:** se permiten terminar; solo se bloquean **viajes nuevos** (ofertas, nearby, asignación).

## Tabla

`line_subscriptions`: `id_line`, `plan`, `status`, `started_at`, `pilot_ends_at`, `next_billing_at`, `last_payment_at`, `notes`, `status_changed_at`, `updated_at`.
