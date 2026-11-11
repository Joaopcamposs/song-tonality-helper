import httpx

from app.main import app

PUBLIC_PATHS = {
    "/api/health",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/auth/verify-email",
}


async def test_every_non_public_api_route_requires_login():
    # O OpenAPI lista todas as rotas, mesmo as de routers incluídos.
    paths = {p: m for p, m in app.openapi()["paths"].items() if p not in PUBLIC_PATHS}
    assert paths, "nenhuma rota protegida encontrada"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for path, methods in paths.items():
            for method in methods:
                url = path.replace("{video_id}", "dQw4w9WgXcQ")
                response = await client.request(method.upper(), url)
                assert response.status_code == 401, f"{method.upper()} {path} está aberta"
