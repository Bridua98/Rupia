# Rupia

```
rupia/
├── rupia/                     # settings, urls, API Ninja, wsgi/asgi
├── inventario/                # ítems, movimientos y ajustes de stock
├── personas/                  # clientes, proveedores y empleados
├── cuentas/                   # cajas y cuentas de efectivo
├── negocio/                   # unidades de negocio
├── core/                      # base compartida
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── filters.py
│   ├── tables.py
│   ├── urls.py
│   ├── api.py
│   ├── menus.py
│   ├── middleware.py
│   ├── routers.py             # SubdomainRouter
│   └── scheduler.py
├── ui/
│   ├── js/
│   │   ├── index.js
│   │   ├── entrypoints/       # un bundle por pantalla
│   │   ├── pages/
│   │   ├── components/
│   │   └── api/
│   ├── scss/main.scss
│   └── webpack.config.js
├── templates/
├── static/
├── manage.py
├── pyproject.toml
├── requirements.txt
├── package.json
└── Makefile
```

Un módulo de negocio es una app en la raíz, plana: `models.py`, `views.py`, `forms.py`, `filters.py`, `tables.py`, `urls.py`, `api.py`. Sin carpetas por formulario.

## Primer acceso

```bash
make bootstrap
```

Aplica las migraciones y crea el superusuario inicial si todavía no existe. En desarrollo, sin variables propias, queda así:

- usuario: `admin`
- correo: `admin@rupia.local`
- contraseña: `Clave-inicial-Rupia-2026`

La pantalla de ingreso está en `/login/`. `/admin/` usa la misma pantalla. Si el usuario ya existe, el comando no cambia su contraseña. Fuera de desarrollo, `DJANGO_SUPERUSER_PASSWORD` es obligatoria.

## Levantar el servidor

Hace falta **Python 3.13** y **[uv](https://docs.astral.sh/uv/)**. Sin `DB_ENGINE=mysql` en el entorno, Django usa SQLite (`db.sqlite3` en la raíz) y no hace falta MySQL.

```bash
uv sync
make bootstrap
uv run python manage.py runserver 0.0.0.0:8000
```

Abrí **http://127.0.0.1:8000/login/**. Las pantallas actuales usan el CSS y el JS de `static/`; npm no es necesario para trabajar en ellas.

Equivalente en Windows, sin Make:

```powershell
uv sync
uv run python manage.py migrate
uv run python manage.py ensure_superuser
uv run python manage.py runserver 0.0.0.0:8000
```

`make install` / `make dev` (o `npm run dev`) suman Webpack y BrowserSync en el puerto **3000**. Ese puerto es el mismo que usa People por defecto: si corrés los dos, cambiá `PEOPLE_API_URL` o el puerto de uno de ellos.

Django no carga un archivo `.env` solo. Las variables (`DB_ENGINE`, `PEOPLE_API_URL`, etc.) tienen que estar en el entorno de la terminal.

## People (padrón de RUC y cédulas)

El alta de personas autocompleta documento, razón social, tipo de documento y fecha de nacimiento contra el servicio **People**. Rupia lo llama en `PEOPLE_API_URL` (por defecto `http://127.0.0.1:3000`).

1. Levantá People en ese origen (o el que uses).
2. Definí la URL si no es la de por defecto:

```powershell
$env:PEOPLE_API_URL = "http://127.0.0.1:3000"
```

```bash
export PEOPLE_API_URL=http://127.0.0.1:3000
```

3. En Rupia, **Personas → Nueva persona**. Escribí documento o razón social: las sugerencias salen de `GET /search?query=...` y la ficha de `GET /?ruc=...`.

Si People no está corriendo, el mantenimiento de personas sigue andando; solo no hay autocompletado del padrón.
