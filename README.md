# Rupia

```
rupia/
├── rupia/                     # settings, urls, API Ninja, wsgi/asgi
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
├── locale/                    # es, en, de
├── docker/
├── manage.py
├── pyproject.toml
├── requirements.txt
├── package.json
├── Makefile
├── docker-compose.yml         # MySQL 8
└── docker-compose.prod.yml
```

Un módulo de negocio es una app en la raíz, plana: `models.py`, `views.py`, `forms.py`, `filters.py`, `tables.py`, `urls.py`, `api.py`. Sin carpetas por formulario.
