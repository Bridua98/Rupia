# Rupia

```
rupia/
├── rupia/                     # settings, urls, API Ninja, wsgi/asgi
├── inventario/                # ítems, movimientos y ajustes de stock
├── personas/                  # clientes, proveedores y empleados
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
