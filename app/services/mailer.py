"""Envio de e-mail pelo Resend (API HTTP); sem chave configurada, o texto só vai para o log."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "Tonalidade <onboarding@resend.dev>"


async def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    """Envia um e-mail (texto e, se vier, HTML); falha de envio é registrada, não derruba."""
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.warning("E-mail (sem RESEND_API_KEY) para %s: %s\n%s", to, subject, text)
        return
    payload = {
        "from": os.environ.get("MAIL_FROM", DEFAULT_FROM),
        "to": [to],
        "subject": subject,
        "text": text,
    }
    if html is not None:
        payload["html"] = html
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                RESEND_URL, headers={"Authorization": f"Bearer {api_key}"}, json=payload
            )
            response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Falha ao enviar e-mail para %s", to)
