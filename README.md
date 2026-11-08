# Rabbit — Backend

API y servidor de tiempo real de **Rabbit**, una plataforma de transporte de mototaxis pensada para la parroquia Betijoque, Venezuela. El backend gestiona líneas de mototaxis, usuarios y roles, solicitudes de viaje, ofertas de conductores, posiciones en tiempo real, tarifas, suscripciones de las líneas y notificaciones push.

Este repositorio contiene **únicamente el backend**. La aplicación móvil y el panel web administrativo viven en el repositorio de frontend.

---

## Enlaces del proyecto

- **Diseño en Figma:** [Ver prototipo en Figma](https://www.figma.com/design/TycvS7GzehRc8mBCVVnrHx/Rabbit?node-id=72-65&t=rsmArw6Ay8rQL1D5-1)
- **Repositorio Frontend:** [Rabbit Flutter](https://github.com/EndelkysAMS/rabbit_flutter)

---

## Características principales

- **Autenticación con JWT** (`/auth/login`, `/auth/register`) usando `djangorestframework-simplejwt`.
- **Gestión de usuarios y roles:** `CLIENT`, `DRIVER`, `ADMIN_LINEA` y `RABBIT_SUPER`.
- **Líneas de mototaxi:** registro de líneas, administradores de línea y conductores asociados.
- **Solicitudes de viaje:** creación, búsqueda de viajes cercanos, asignación de conductor, cambios de estado y calificaciones.
- **Ofertas de conductores:** los conductores pueden ofertar por una solicitud y consultar las ofertas de un viaje.
- **Posiciones en tiempo real:** seguimiento de la ubicación de los conductores con soporte geoespacial (GIS).
- **Tiempo real con Socket.IO:** notificaciones de viajes, ofertas y posiciones sobre Django Channels + Redis.
- **Panel de administración de línea:** dashboard, viajes, clientes, conductores, tarifas y exportaciones CSV.
- **Super administración Rabbit:** gestión de líneas y suscripciones (planes `piloto`, `basico`, `pro`).
- **Suscripción B2B2C por línea:** cobro manual, estados `activa`, `morosa` y `suspendida`.
- **Notificaciones push** con Firebase Cloud Messaging (opcional en desarrollo).

---

## Tecnologías

| Componente | Tecnología |
|------------|------------|
| Framework web | Django 5 + Django REST Framework |
| Autenticación | JWT (SimpleJWT) |
| Tiempo real | Django Channels + python-socketio + Redis |
| Base de datos | MySQL con soporte espacial (GIS) |
| GIS | GDAL / GEOS (`django.contrib.gis`) |
| Notificaciones | Firebase Admin SDK |
| Utilidades | python-dotenv, bcrypt, requests |

---

## Estructura del proyecto

```text
DjangoRabbitServer/
├── DjangoRabbitServer/      # Configuración, URLs, ASGI y WSGI
├── authentication/          # Login y registro con JWT
├── users/                   # Usuarios, líneas, suscripciones y paneles admin
├── roles/                   # Roles de la plataforma
├── client_requests/         # Solicitudes de viaje y tarifas
├── driver_trip_offers/      # Ofertas de los conductores
├── driver_position/         # Posiciones de conductores (GIS)
├── driver_bike_info/        # Información de la moto del conductor
├── time_and_distance_values/# Tiempo y distancia de referencia
├── firebase_notification/   # Notificaciones push
├── socketio_app/            # Eventos Socket.IO en tiempo real
├── docs/                    # Documentación adicional de la API
├── media/                   # Archivos subidos (ignorado por Git)
├── manage.py
└── requirements.txt
```

---

## Requisitos previos

Antes de ejecutar el proyecto asegúrate de tener instalado:

- **Python 3.10 o superior**
- **MySQL 8** con soporte espacial
- **Redis** (para el canal de tiempo real)
- **GDAL y GEOS**
  - Windows: instalar [OSGeo4W](https://trac.osgeo.org/osgeo4w/) y ajustar las rutas en `DjangoRabbitServer/settings.py`.
  - macOS: `brew install gdal geos`
  - Linux: `sudo apt install gdal-bin libgdal-dev libgeos-dev`
- **Firebase** (opcional): archivo de cuenta de servicio para habilitar las notificaciones push.

---

## Cómo ejecutar el proyecto

### 1. Clonar el repositorio

```bash
git clone https://github.com/EndelkysAMS/rabbit_backend.git
cd rabbit_backend
```

### 2. Crear y activar un entorno virtual

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

> En Windows, `mysqlclient` puede requerir las herramientas de compilación de MySQL. Si tienes problemas, instala primero el conector de MySQL o usa una rueda precompilada compatible con tu versión de Python.

### 4. Configurar las variables de entorno

Copia el archivo de ejemplo y completa tus valores locales:

```bash
cp .env.example .env
```

Variables principales de `.env`:

| Variable | Descripción |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Clave secreta de Django |
| `DJANGO_DEBUG` | `True` en desarrollo, `False` en producción |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos, separados por coma |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Conexión a MySQL |
| `REDIS_HOST`, `REDIS_PORT` | Conexión a Redis |
| `GOOGLE_MAPS_API_KEY` | Clave de Google Maps (opcional) |
| `FIREBASE_SERVICE_ACCOUNT` | Ruta al archivo de cuenta de servicio de Firebase (opcional) |

> **Importante:** no subas contraseñas, claves secretas ni claves de API al repositorio. El archivo `.env` ya está incluido en `.gitignore`.

### 5. Crear la base de datos

Crea una base de datos MySQL (por ejemplo `rabbit_db`) con soporte espacial y usa las credenciales configuradas en `.env`.

### 6. Configurar los servicios externos

- **Redis:** debe estar corriendo en `127.0.0.1:6379` (o ajusta `REDIS_HOST` y `REDIS_PORT` en `.env`).
- **Firebase (opcional):** coloca el archivo de cuenta de servicio en la raíz del proyecto con el nombre `firebase-service-account.json`, o define `FIREBASE_SERVICE_ACCOUNT` con la ruta del archivo. Si no existe, el servidor arranca igual, pero las notificaciones push quedan deshabilitadas.
- **Google Maps (opcional):** la integración de distancias y tiempos requiere una clave de API. Defínela en `GOOGLE_MAPS_API_KEY` dentro de `.env`; **no la escribas en el README ni la versiones en Git**.

```bash
# Ejemplo (Windows PowerShell)
$env:GOOGLE_MAPS_API_KEY = "tu-clave-aqui"

# Ejemplo (macOS / Linux)
export GOOGLE_MAPS_API_KEY="tu-clave-aqui"
```

### 7. Aplicar las migraciones

```bash
python manage.py migrate
```

### 8. Ejecutar el servidor

Para levantar la API REST en el puerto `3000`:

```bash
python manage.py runserver 0.0.0.0:3000
```

Para habilitar también los WebSockets de Socket.IO, ejecuta el proyecto con un servidor ASGI (por ejemplo Uvicorn):

```bash
pip install "uvicorn[standard]"
uvicorn DjangoRabbitServer.asgi:application --host 0.0.0.0 --port 3000
```

La API quedará disponible en `http://localhost:3000` y el endpoint de Socket.IO en `/socket.io/`.

---

## Endpoints principales

| Prefijo | Descripción |
|---------|-------------|
| `/auth` | Registro e inicio de sesión |
| `/users` | Perfil, usuarios y tokens de notificación |
| `/admin-linea` | Panel del administrador de línea |
| `/admin/super` | Panel del super administrador Rabbit |
| `/drivers-position` | Posiciones de los conductores |
| `/client-requests` | Solicitudes de viaje y tarifas |
| `/driver-trip-offers` | Ofertas de viaje de los conductores |
| `/driver-bike-info` | Información de la moto |
| `/firebase-notification` | Notificaciones push |
| `/socket.io/` | Conexión de tiempo real (Socket.IO) |

La documentación detallada de los endpoints del panel de línea está disponible en [`docs/ADMIN_LINEA_API.md`](docs/ADMIN_LINEA_API.md). El modelo de suscripciones se describe en [`docs/SUBSCRIPTION_B2B2C.md`](docs/SUBSCRIPTION_B2B2C.md).

---

## Notas de seguridad

- No se incluyen claves de API, contraseñas ni credenciales en este documento.
- El archivo `firebase-service-account.json`, los archivos `.env`, `db.sqlite3` y la carpeta `media/` están excluidos por `.gitignore`.
- Antes de desplegar en producción, cambia `SECRET_KEY`, desactiva `DEBUG`, restringe `ALLOWED_HOSTS` y configura HTTPS.
- Si una clave de API llegó a exponerse, rótala de inmediato y muévela a una variable de entorno.

---

## Licencia

Este proyecto está bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más información.
