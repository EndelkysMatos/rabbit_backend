# Prompt completo — admin-web Rabbit (ADMIN_LINEA + RABBIT_SUPER)

Copia este documento al agente de frontend. Proyecto: `rabbit_flutter/admin-web` (React + Vite + TypeScript + React Router + TanStack Query).

**API base:** `VITE_API_BASE_URL` (ej. `http://127.0.0.1:3000` o `http://localhost:3000`)  
**Auth:** `POST /auth/login` → guardar `token` tal cual (`Bearer eyJ...`) en `localStorage` key `rabbit_admin_token`.

---

## 1. Diseño visual (obligatorio)

Paleta Rabbit / mototaxi (CSS variables en `:root`):

```css
--color-primary: #FFC107;
--color-primary-dark: #F9A825;
--color-accent: #FF6F00;
--color-sidebar: #1E293B;
--color-bg: #F4F6F8;
--color-success: #16A34A;
--color-warning: #EA580C;
--color-danger: #DC2626;
```

Layout: sidebar oscuro + header claro. Tipografía Inter o DM Sans. Cards con `border-radius: 12px`.

---

## 2. Roles e iconos (login / selector)

| Rol | id | route | Icono |
|-----|-----|-------|-------|
| Cliente | CLIENT | client/home | URL Flaticon existente |
| Conductor | DRIVER | driver/home | URL Flaticon existente |
| Admin línea | ADMIN_LINEA | admin-linea/home | URL Flaticon existente |
| **Super Admin Rabbit** | **RABBIT_SUPER** | **super/home** | **`/roles/rabbit_super_role.png`** (public) o URL API `/media/roles/rabbit_super_role.png` |

Imagen generada para RABBIT_SUPER: escudo amarillo/naranja estilo app (ya en `public/roles/rabbit_super_role.png`).

En login, si el usuario tiene **varios roles**, mostrar tarjetas con icono + nombre de rol y redirigir según selección (o auto-redirigir si solo tiene uno).

---

## 3. Enrutamiento por rol (CRÍTICO)

### 3.1 ADMIN_LINEA → panel `/dashboard`, `/plan`, etc.

Helper existente: `isAdminLineaRole(roles)` — ajustar para **excluir** `RABBIT_SUPER` si el usuario solo debe entrar al panel super cuando elige ese rol.

```ts
export function isAdminLineaRole(roles: Role[]): boolean {
  return roles.some(r => String(r.id).toUpperCase() === 'ADMIN_LINEA');
}

export function isRabbitSuperRole(roles: Role[]): boolean {
  return roles.some(r => String(r.id).toUpperCase() === 'RABBIT_SUPER');
}
```

**Login flow:**
- Si `isRabbitSuperRole` && !`isAdminLineaRole` → `/super/lines`
- Si `isAdminLineaRole` → `/dashboard`
- Si ambos → pantalla "¿Entrar como Admin Línea o Super Rabbit?" o preferir super si URL `/super`
- Si ninguno → toast "Acceso denegado"

### 3.2 PrivateRoute

- `PrivateRoute` (ADMIN_LINEA): exige `ADMIN_LINEA`
- `SuperPrivateRoute` (nuevo): exige `RABBIT_SUPER`

---

## 4. Panel ADMIN_LINEA (ya parcialmente implementado — completar)

### Páginas existentes

| Ruta | Página | API principal |
|------|--------|---------------|
| `/login` | LoginPage | POST `/auth/login` |
| `/dashboard` | DashboardPage | GET `/admin-linea/dashboard` |
| `/plan` | SubscriptionPage | GET `/admin-linea/dashboard` (usar `line.subscription`) |
| `/drivers` | Activos | GET `/admin-linea/drivers` |
| `/drivers/inactive` | Inactivos | GET `/admin-linea/drivers?is_active=false` |
| `/drivers/new` | Alta | POST `/admin-linea/drivers` |
| `/drivers/:id` | Editar | GET/PATCH `/admin-linea/drivers/:id` |
| `/map` | Mapa | GET `/admin-linea/drivers/positions` |
| `/trips` | Viajes | GET `/admin-linea/trips` |
| `/trips/:id` | Detalle | GET `/admin-linea/trips/:id` |
| `/clients` | Clientes | GET `/admin-linea/clients` |
| `/fares` | Tarifas | GET/PATCH `/admin-linea/fares` |
| `/profile` | Perfil admin | PATCH `/admin-linea/profile` |

### 4.1 SubscriptionPage — conectar datos REALES (prioridad)

**Eliminar** `DEFAULT_SUBSCRIPTION` para plan/status actuales.

```ts
interface LineSubscription {
  plan: 'piloto' | 'basico' | 'pro';
  status: 'activa' | 'morosa' | 'suspendida';
  started_at?: string | null;
  pilot_ends_at?: string | null;
  next_billing_at?: string | null;
  last_payment_at?: string | null;
  days_until_pilot_end?: number | null;
  max_drivers?: number | null;
  active_drivers_count?: number;
}

// data.line.subscription desde getDashboard()
const sub = data?.line?.subscription;
const plan = sub?.plan ?? 'piloto';
const status = sub?.status ?? 'activa';
```

**UI obligatoria en `/plan`:**
- Badge status: activa (verde), morosa (naranja), suspendida (rojo)
- Piloto: chip "Quedan {days_until_pilot_end} días de piloto"
- Límite: "Conductores {active_drivers_count}/{max_drivers}" si `max_drivers != null`
- Fechas: `last_payment_at`, `next_billing_at` formateadas es-VE
- Banner alert si `status !== 'activa'`
- Mantener `PLANS` de `config/subscription.ts` solo para textos de tarjetas comparativas

### 4.2 Dashboard — métricas

Respuesta `GET /admin-linea/dashboard`:

```json
{
  "line": {
    "id": 1,
    "name": "San Benito",
    "km_value": 0.5,
    "min_value": 0.2,
    "subscription": { "...": "LineSubscription" }
  },
  "drivers": { "active", "inactive", "with_live_position" },
  "trips": { "total", "created", "in_progress", "finished", "cancelled", "today" },
  "revenue": { "total_finished_usd", "today_finished_usd" }
}
```

### 4.3 Errores de suscripción en conductores

POST `/admin-linea/drivers` puede retornar **403**:
- `"Línea suspendida. Contacte a Rabbit."`
- `"Límite del plan Piloto (15 conductores)"`

Mostrar toast con el `message` del backend.

---

## 5. Panel RABBIT_SUPER (NUEVO — construir completo)

Prefijo rutas: **`/super/*`**. Mismo login (`POST /auth/login`) con usuario que tenga rol `RABBIT_SUPER`.

### 5.1 API super-admin (solo RABBIT_SUPER)

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/admin/super/lines` | Listar todas las líneas + subscription |
| PATCH | `/admin/super/lines/{id}/subscription` | Editar plan/status/fechas/notas |
| POST | `/admin/super/lines/{id}/subscription/record-payment` | Registrar pago manual |
| POST | `/admin/super/lines/{id}/subscription/activate` | Activar línea |
| POST | `/admin/super/lines/{id}/subscription/suspend` | Suspender línea |

**GET `/admin/super/lines` → array:**

```json
[
  {
    "id": 1,
    "name": "San Benito",
    "created_at": "...",
    "updated_at": "...",
    "subscription": {
      "plan": "basico",
      "status": "activa",
      "started_at": "...",
      "pilot_ends_at": "...",
      "next_billing_at": "...",
      "last_payment_at": "...",
      "days_until_pilot_end": 83,
      "max_drivers": null,
      "active_drivers_count": 1
    }
  }
]
```

**POST record-payment body:**

```json
{
  "plan": "basico",
  "last_payment_at": "2026-04-02T10:00:00Z",
  "notes": "Pagó abril — transferencia Banco X"
}
```

Enums **exactos** (minúsculas, sin tildes):  
`plan`: piloto | basico | pro  
`status`: activa | morosa | suspendida

### 5.2 Páginas super-admin a crear

| Ruta | Contenido |
|------|-----------|
| `/super/lines` | Tabla: línea, plan, status (badge), conductores, pilot countdown, próximo cobro, acciones |
| `/super/lines/:id` | Detalle + formulario editar subscription + botones Activar / Suspender / Registrar pago |

**Acciones por fila:**
- "Registrar pago" → modal con plan, notas, fecha opcional → POST record-payment
- "Suspender" → POST suspend (confirmación)
- "Activar" → POST activate
- "Editar" → PATCH subscription

**Diseño:** mismo shell visual Rabbit pero sidebar distinto:
- Líneas
- (futuro) Usuarios Rabbit

Header: logo + "Rabbit Super Admin" + avatar usuario + logout.

**Credencial prueba:** `super-admin@example.com` (rol RABBIT_SUPER asignado en BD).

### 5.3 API client (`src/api/super.ts`)

```ts
export async function getSuperLines(): Promise<SuperLine[]>
export async function patchLineSubscription(id: number, body: PatchSubscriptionBody)
export async function recordLinePayment(id: number, body: RecordPaymentBody)
export async function activateLine(id: number)
export async function suspendLine(id: number)
```

---

## 6. Types (`src/types/index.ts`)

Añadir/actualizar:

```ts
export interface LineSubscription { ... } // ver arriba

export interface LineInfo {
  id: number;
  name: string;
  km_value?: number;
  min_value?: number;
  subscription?: LineSubscription;
}

export interface SuperLine {
  id: number;
  name: string;
  created_at: string;
  updated_at: string;
  subscription: LineSubscription;
}
```

---

## 7. Archivos a crear/modificar (checklist)

### ADMIN_LINEA
- [ ] `types/index.ts` — LineSubscription en DashboardData.line
- [ ] `SubscriptionPage.tsx` — datos reales, sin DEFAULT_SUBSCRIPTION para plan/status
- [ ] `AdminLayout.tsx` — badge en sidebar "Mi plan" si subscription.status !== 'activa'
- [ ] `Sidebar.tsx` — link /plan

### RABBIT_SUPER (nuevo)
- [ ] `api/super.ts`
- [ ] `hooks/useAuth.tsx` — helpers de rol (opcional `activePortal: 'linea' | 'super'`)
- [ ] `components/SuperPrivateRoute.tsx`
- [ ] `components/layout/SuperLayout.tsx` + `SuperSidebar.tsx`
- [ ] `pages/super/SuperLinesPage.tsx`
- [ ] `pages/super/SuperLineDetailPage.tsx`
- [ ] `App.tsx` — rutas `/super/*`
- [ ] `LoginPage.tsx` — routing multi-rol + iconos de rol
- [ ] `public/roles/rabbit_super_role.png` — ya existe

### Auth
- [ ] `api/auth.ts` — `isRabbitSuperRole`, refinar `isAdminLineaRole` (id exacto ADMIN_LINEA)

---

## 8. Criterios de aceptación

**ADMIN_LINEA** (`admin-linea@example.com` / `<contraseña>`):
- [ ] Login → `/dashboard`
- [ ] `/plan` muestra plan/status/countdown desde API
- [ ] Métricas dashboard con trips.today y revenue.today_finished_usd
- [ ] CRUD conductores activos/inactivos

**RABBIT_SUPER** (`super-admin@example.com`):
- [ ] Login → `/super/lines`
- [ ] Lista todas las líneas con subscription
- [ ] Registrar pago → línea pasa a activa + fechas actualizadas
- [ ] Suspender → admin línea no puede crear conductores (403)

**General:**
- [ ] Misma paleta amarillo/naranja Rabbit
- [ ] Errores API como toast con `message`
- [ ] CORS OK desde localhost:5173

---

## 9. Fuera de alcance

- Pasarela de pago (Stripe/PayPal)
- Factura PDF
- App móvil Flutter (no modificar)

---

## 10. Referencia backend

- `docs/ADMIN_LINEA_API.md`
- `docs/SUBSCRIPTION_B2B2C.md`
- Imagen rol super: `GET {API}/media/roles/rabbit_super_role.png`
