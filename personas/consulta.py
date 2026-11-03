import json
from datetime import datetime
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from personas.models import TipoDocumento

TIMEOUT = 4


def _url(path, params):
    base = getattr(settings, "PEOPLE_API_URL", "http://127.0.0.1:3000").rstrip("/")
    target = base + (path if path.startswith("/") else "/" + path)
    if params:
        target += "?" + urlencode(params)
    return target


def _get(path, params):
    request = Request(_url(path, params), headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except (OSError, URLError, TimeoutError, ValueError):
        return None


def _fecha(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def ficha_persona(data):
    if not isinstance(data, dict):
        return None
    ruc = str(data.get("ruc") or "").strip()
    if not ruc:
        return None
    dv = data.get("dv")
    dv = str(dv).strip() if dv not in (None, "") else ""
    if dv:
        tipo = TipoDocumento.RUC
        documento = f"{ruc}-{dv}"
    else:
        tipo = TipoDocumento.CEDULA
        documento = ruc
    razon_social = str(data.get("razonsocial") or "").strip()
    return {
        "ruc": ruc,
        "tipo_documento": tipo,
        "documento": documento,
        "razon_social": razon_social,
        "fecha_nacimiento": _fecha(data.get("fecNac")),
        "label": f"{razon_social} ({documento})" if razon_social else documento,
    }


def buscar(query):
    query = (query or "").strip()
    if not query:
        return []
    data = _get("/search", {"query": query})
    if not isinstance(data, list):
        return []
    results = []
    for row in data:
        ficha = ficha_persona(row)
        if ficha:
            results.append(ficha)
        if len(results) == 10:
            break
    return results


def consultar_ruc(ruc):
    ruc = (ruc or "").strip()
    if not ruc:
        return None
    data = _get("/", {"ruc": ruc})
    if not isinstance(data, dict):
        return None
    return ficha_persona(data)
