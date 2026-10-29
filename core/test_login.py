import pytest


@pytest.mark.django_db
def test_login_muestra_el_formulario(client):
    response = client.get("/login/")

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ingresar" in content
    assert "css/rupia.css" in content
    assert "csrfmiddlewaretoken" in content
    assert "Clave-inicial-Rupia-2026" not in content


@pytest.mark.django_db
def test_la_raiz_pide_ingreso(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.url == "/login/?next=/"


@pytest.mark.django_db
def test_login_rechaza_clave_incorrecta(client, django_user_model):
    django_user_model.objects.create_user("ada", "ada@rupia.local", "Clave-inicial-Rupia-2026")

    response = client.post("/login/", {"username": "ada", "password": "no-es-la-clave"})

    assert response.status_code == 200
    assert "no coinciden" in response.content.decode()
    assert client.get("/").status_code == 302


@pytest.mark.django_db
def test_login_exige_los_campos(client):
    response = client.post("/login/", {"username": "", "password": ""})

    assert response.status_code == 200
    assert "obligatorio" in response.content.decode()


@pytest.mark.django_db
def test_login_entra_y_cierra_sesion(client, django_user_model):
    django_user_model.objects.create_user("ada", "ada@rupia.local", "Clave-inicial-Rupia-2026")

    response = client.post(
        "/login/",
        {"username": "ada", "password": "Clave-inicial-Rupia-2026"},
    )

    assert response.status_code == 302
    assert response.url == "/"
    home = client.get("/")
    assert home.status_code == 200
    assert "Hola, ada." in home.content.decode()
    assert "Abrir administración" not in home.content.decode()

    logout = client.post("/logout/")
    assert logout.status_code == 302
    assert logout.url == "/login/"
    assert client.get("/").status_code == 302
    assert client.get("/logout/").status_code == 405


@pytest.mark.django_db
def test_el_administrador_ve_el_panel(client, django_user_model):
    admin = django_user_model.objects.create_superuser(
        "admin",
        "admin@rupia.local",
        "Clave-inicial-Rupia-2026",
    )
    client.force_login(admin)

    response = client.get("/")

    content = response.content.decode()
    assert response.status_code == 200
    assert "Administración" in content
    assert 'href="/admin/"' in content


@pytest.mark.django_db
def test_login_respeta_next_y_bloquea_redirecciones_externas(client, django_user_model):
    django_user_model.objects.create_superuser(
        "admin",
        "admin@rupia.local",
        "Clave-inicial-Rupia-2026",
    )

    response = client.post(
        "/login/",
        {
            "username": "admin",
            "password": "Clave-inicial-Rupia-2026",
            "next": "/admin/",
        },
    )
    assert response.status_code == 302
    assert response.url == "/admin/"

    client.logout()
    external = client.post(
        "/login/",
        {
            "username": "admin",
            "password": "Clave-inicial-Rupia-2026",
            "next": "https://evil.example/robo",
        },
    )
    assert external.status_code == 302
    assert external.url == "/"


@pytest.mark.django_db
def test_quien_ya_ingreso_no_vuelve_al_formulario(client, django_user_model):
    admin = django_user_model.objects.create_superuser(
        "admin",
        "admin@rupia.local",
        "Clave-inicial-Rupia-2026",
    )
    client.force_login(admin)

    response = client.get("/login/?next=/admin/")

    assert response.status_code == 302
    assert response.url == "/admin/"


@pytest.mark.django_db
def test_admin_usa_la_misma_pantalla(client):
    response = client.get("/admin/login/?next=/admin/")

    assert response.status_code == 302
    assert response.url == "/login/?next=/admin/"

    followed = client.get("/admin/", follow=True)
    assert followed.status_code == 200
    assert "Ingresar" in followed.content.decode()


@pytest.mark.django_db
def test_un_usuario_comun_no_entra_en_bucle_con_el_admin(client, django_user_model):
    user = django_user_model.objects.create_user(
        "ada",
        "ada@rupia.local",
        "Clave-inicial-Rupia-2026",
    )
    client.force_login(user)

    response = client.get("/admin/", follow=True)

    assert response.status_code == 200
    assert "Tu sesión quedó abierta." in response.content.decode()


@pytest.mark.django_db
def test_cuenta_inactiva_no_ingresa(client, django_user_model):
    django_user_model.objects.create_user(
        "ada",
        "ada@rupia.local",
        "Clave-inicial-Rupia-2026",
        is_active=False,
    )

    response = client.post(
        "/login/",
        {"username": "ada", "password": "Clave-inicial-Rupia-2026"},
    )

    assert response.status_code == 200
    assert "no coinciden" in response.content.decode()
    assert client.get("/").status_code == 302
