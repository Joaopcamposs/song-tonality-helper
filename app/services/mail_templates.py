"""Corpo dos e-mails de ação (confirmar e-mail, redefinir senha): versão em texto e em HTML."""

# ruff: noqa: E501
from html import escape


def action_email(
    name: str, heading: str, intro: str, button: str, link: str, notice: str
) -> tuple[str, str]:
    """Monta o e-mail de uma ação com link: devolve `(texto, html)` com o mesmo conteúdo.

    O HTML usa tabela e estilo inline, que é o que os clientes de e-mail aceitam; o texto
    é o alternativo de quem não vê HTML.
    """
    text = f"Olá, {name}!\n\n{intro}\n\n{button}: {link}\n\n{notice}\n"
    html = f"""<!doctype html>
<html lang="pt-BR">
  <body style="margin:0;padding:32px 16px;background:#eaf0fa;font-family:Arial,Helvetica,sans-serif;color:#0e1624;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:20px;overflow:hidden;">
      <tr>
        <td style="padding:28px 32px;background:#0e1624;color:#ffffff;">
          <span style="display:inline-block;padding:6px 12px;border-radius:999px;background:rgba(255,255,255,0.14);font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Tonalidade</span>
          <h1 style="margin:18px 0 8px;font-size:28px;line-height:1.15;">{escape(heading)}</h1>
          <p style="margin:0;font-size:15px;line-height:1.6;color:rgba(255,255,255,0.88);">Olá, {escape(name)}!</p>
        </td>
      </tr>
      <tr>
        <td style="padding:32px;">
          <p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:#334155;">{escape(intro)}</p>
          <p style="margin:0 0 24px;text-align:center;">
            <a href="{escape(link)}" style="display:inline-block;background:#4c9aff;color:#031a38;text-decoration:none;padding:14px 28px;border-radius:12px;font-weight:700;font-size:15px;">{escape(button)}</a>
          </p>
          <p style="margin:0 0 24px;padding:14px 16px;border-radius:12px;background:#eaf3ff;border:1px solid #c7defc;font-size:13px;line-height:1.6;color:#1e4f8f;">{escape(notice)}</p>
          <p style="margin:0 0 6px;font-size:12px;line-height:1.5;color:#64748b;">Se o botão não abrir, copie este endereço no navegador:</p>
          <p style="margin:0;font-size:12px;line-height:1.5;word-break:break-all;"><a href="{escape(link)}" style="color:#2563eb;">{escape(link)}</a></p>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    return text, html
