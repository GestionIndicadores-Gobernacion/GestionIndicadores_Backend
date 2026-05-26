# app/modules/support/services/email_sender.py
"""
Envío de correos para el módulo de soporte.

Usa SMTP vía stdlib (smtplib + email.message) para no añadir dependencias.
Para Gmail se requiere una App Password (https://myaccount.google.com/apppasswords)
con 2FA activado en la cuenta.
"""

import base64
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from flask import current_app

logger = logging.getLogger(__name__)


class SmtpNotConfiguredError(RuntimeError):
    """Se levanta cuando faltan credenciales SMTP en la configuración."""


_ALLOWED_IMAGE_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 5 MB


def _parse_data_url(data_url: str):
    """
    Convierte un data-URL (`data:image/png;base64,XXXX`) en (mime, bytes).
    Devuelve (None, None) si el formato no es válido o supera el tope.
    """
    if not data_url or not isinstance(data_url, str):
        return None, None

    if not data_url.startswith("data:"):
        return None, None

    try:
        header, b64data = data_url.split(",", 1)
    except ValueError:
        return None, None

    # header tipo "data:image/png;base64"
    meta = header[5:]  # quitar "data:"
    parts = meta.split(";")
    mime = parts[0].strip().lower() if parts else ""

    if mime not in _ALLOWED_IMAGE_MIME:
        return None, None

    # Solo aceptamos base64
    if "base64" not in [p.strip().lower() for p in parts[1:]]:
        return None, None

    try:
        raw = base64.b64decode(b64data, validate=True)
    except (ValueError, base64.binascii.Error):
        return None, None

    if len(raw) > _MAX_ATTACHMENT_BYTES:
        return None, None

    # Normalizar image/jpg → image/jpeg para subtype
    if mime == "image/jpg":
        mime = "image/jpeg"

    return mime, raw


def send_support_report(
    *,
    reporter_name: str,
    reporter_email: str,
    reporter_role: str,
    message_text: str,
    current_url: str,
    user_agent: str,
    screenshot_data_url: str | None,
    ticket_id: int | None = None,
):
    """
    Envía el correo de reporte al destinatario configurado.

    Levanta SmtpNotConfiguredError si faltan credenciales,
    o smtplib.SMTPException si falla el envío.
    """
    cfg = current_app.config
    host = cfg.get("SMTP_HOST")
    port = int(cfg.get("SMTP_PORT") or 587)
    user = cfg.get("SMTP_USER")
    password = cfg.get("SMTP_PASSWORD")
    to_addr = cfg.get("SUPPORT_EMAIL_TO")
    from_name = cfg.get("SUPPORT_EMAIL_FROM_NAME") or "Indicadores PYBA"

    if not (host and user and password and to_addr):
        raise SmtpNotConfiguredError(
            "Faltan SMTP_USER / SMTP_PASSWORD / SUPPORT_EMAIL_TO en la configuración."
        )

    msg = EmailMessage()
    ticket_tag = f"#{ticket_id} · " if ticket_id else ""
    subject = f"[Reporte {ticket_tag}{reporter_name}]"
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, user))
    msg["To"] = to_addr
    msg["Reply-To"] = reporter_email or user
    msg["Message-ID"] = make_msgid(domain="indicadorespyba")

    # Cuerpo en texto plano (fallback) + HTML
    plain_lines = [
        "Nuevo reporte recibido desde la plataforma Indicadores PYBA.",
        "",
        f"Usuario:    {reporter_name}",
        f"Email:      {reporter_email}",
        f"Rol:        {reporter_role}",
        f"URL:        {current_url or '(no especificada)'}",
        f"Navegador:  {user_agent or '(no especificado)'}",
        "",
        "─── Mensaje ─────────────────────────────────",
        message_text,
        "─────────────────────────────────────────────",
    ]
    msg.set_content("\n".join(plain_lines))

    safe_msg = (
        message_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    safe_url = (current_url or "").replace("<", "&lt;").replace(">", "&gt;")
    safe_ua = (user_agent or "").replace("<", "&lt;").replace(">", "&gt;")

    html = f"""\
<!doctype html>
<html>
<body style="font-family:Segoe UI,Helvetica,Arial,sans-serif;background:#f5f7fb;padding:24px;color:#1B3A6B;">
  <div style="max-width:640px;margin:0 auto;background:#fff;border:1px solid #D6E0F0;border-radius:12px;overflow:hidden;">
    <div style="background:linear-gradient(90deg,#1B3A6B,#2d5fa8);color:#fff;padding:18px 22px;">
      <div style="font-size:12px;letter-spacing:1px;opacity:.85;">INDICADORES PYBA · SOPORTE</div>
      <div style="font-size:18px;font-weight:700;margin-top:4px;">Nuevo reporte de fallo</div>
    </div>
    <div style="padding:22px;">
      <table style="width:100%;font-size:13px;border-collapse:collapse;">
        <tr><td style="padding:6px 0;color:#4A6A9B;width:110px;">Usuario</td><td style="padding:6px 0;font-weight:600;">{reporter_name}</td></tr>
        <tr><td style="padding:6px 0;color:#4A6A9B;">Email</td><td style="padding:6px 0;"><a href="mailto:{reporter_email}" style="color:#2d5fa8;">{reporter_email}</a></td></tr>
        <tr><td style="padding:6px 0;color:#4A6A9B;">Rol</td><td style="padding:6px 0;">{reporter_role}</td></tr>
        <tr><td style="padding:6px 0;color:#4A6A9B;">URL</td><td style="padding:6px 0;word-break:break-all;">{safe_url or '<i>(no especificada)</i>'}</td></tr>
        <tr><td style="padding:6px 0;color:#4A6A9B;vertical-align:top;">Navegador</td><td style="padding:6px 0;font-size:11px;color:#4A6A9B;word-break:break-all;">{safe_ua or '<i>(no especificado)</i>'}</td></tr>
      </table>
      <div style="margin-top:18px;padding:14px;background:#F8FAFD;border:1px solid #EDF2FA;border-radius:8px;font-size:14px;line-height:1.5;color:#1B3A6B;white-space:pre-wrap;">
        {safe_msg}
      </div>
    </div>
    <div style="padding:12px 22px;background:#F8FAFD;border-top:1px solid #EDF2FA;font-size:11px;color:#4A6A9B;">
      Este correo fue generado automáticamente por el botón de soporte del sistema.
    </div>
  </div>
</body>
</html>
"""
    msg.add_alternative(html, subtype="html")

    if screenshot_data_url:
        mime, raw = _parse_data_url(screenshot_data_url)
        if mime and raw:
            maintype, subtype = mime.split("/", 1)
            msg.add_attachment(
                raw,
                maintype=maintype,
                subtype=subtype,
                filename=f"captura.{subtype if subtype != 'jpeg' else 'jpg'}",
            )
        else:
            logger.info("support: screenshot adjunto descartado por formato/tamaño inválido.")

    context = ssl.create_default_context()
    # Conexión + STARTTLS (estándar en 587). Para SSL directo (puerto 465)
    # cambiar a smtplib.SMTP_SSL.
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(user, password)
            server.send_message(msg)
