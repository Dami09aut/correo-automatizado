import imaplib
import email
from email.header import decode_header
import datetime
import csv
import os
from dotenv import load_dotenv
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from email.utils import parseaddr

load_dotenv()

# Credenciales
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
IMAP_SERVER = "imap.gmail.com"

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")
TWILIO_TO = os.getenv("TWILIO_TO")

def conectar_imap():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL, PASSWORD)
        print("✅ Conexión IMAP exitosa.")
        return mail
    except Exception as e:
        print(f"❌ Error al conectar por IMAP: {e}")
        return None

def clasificar_correo(asunto, cuerpo):
    texto = f"{asunto} {cuerpo}".lower()
    if "urgente" in texto or "importante" in texto:
        return "IMPORTANTE"
    elif "factura" in texto or "pago" in texto:
        return "FINANZAS"
    elif "reunión" in texto or "cita" in texto:
        return "REUNIÓN"
    else:
        return "OTROS"

def enviar_respuesta(destinatario):
    try:
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT") or "465")
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")

        msg = MIMEText("Gracias por tu mensaje. Hemos recibido tu correo y te responderemos pronto.".encode("utf-8"), _charset="utf-8")

        msg["Subject"] = Header("Re: Respuesta automática", "utf-8")
        msg["From"] = formataddr((str(Header("Auto Respuesta", "utf-8")), smtp_user))
        correo_destino = parseaddr(destinatario)[1]
        if not correo_destino or "@" not in correo_destino:
            raise ValueError(f"Dirección inválida: {destinatario}")
        msg["To"] = correo_destino

        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, correo_destino, msg.as_string())

        print("📤 Respuesta automática enviada.")

    except Exception as e:
        print(f"❌ Error al enviar respuesta automatica: {e}")

def enviar_whatsapp(asunto, de, categoria):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        body = f"Nuevo correo IMPORTANTE\nDe: {de}\nAsunto: {asunto}\nCategoría: {categoria}"

        # Convertir el texto solo a ASCII para evitar errores de codificación en Render
        body = body.encode('ascii', 'ignore').decode('ascii')

        mensaje = client.messages.create(
            from_=TWILIO_FROM,
            to=TWILIO_TO,
            body=body
        )
        print("📲 WhatsApp enviado correctamente.")
    except Exception as e:
        print(f"❌ Error al enviar WhatsApp: {e}")

def guardar_registro(fecha, remitente, asunto, categoria, respuesta):
    archivo = "registro_correos.csv"
    encabezados = ["Fecha", "Remitente", "Asunto", "Importante", "Respuesta Enviada"]
    datos = [fecha, remitente, asunto, "Sí" if categoria == "IMPORTANTE" else "No", "Sí" if respuesta else "No"]

    existe = os.path.isfile(archivo)
    with open(archivo, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(encabezados)
        writer.writerow(datos)

def leer_correos():
    mail = conectar_imap()
    if not mail:
        return

    mail.select("inbox")
    status, mensajes = mail.search(None, 'UNSEEN')
    correos = mensajes[0].split()

    print(f"📨 Correos no leídos encontrados: {len(correos)}")

    for num in correos:
        status, data = mail.fetch(num, "(RFC822)")
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)

        from_raw = msg.get("From")
        from email.utils import parseaddr
        nombre_remitente, correo_remitente = parseaddr(from_raw)
        de = correo_remitente
        from_decoded, encoding = decode_header(from_raw)[0]
        if isinstance(from_decoded, bytes):
            from_decoded = from_decoded.decode(encoding if encoding else "utf-8")
        asunto, encoding = decode_header(msg.get("Subject"))[0]
        if isinstance(asunto, bytes):
            asunto = asunto.decode(encoding if encoding else "utf-8")

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    cuerpo = part.get_payload(decode=True).decode()
                    break
        else:
            cuerpo = msg.get_payload(decode=True).decode()

        categoria = clasificar_correo(asunto, cuerpo)
        fecha = msg.get("Date")

        print("🔔", "IMPORTANTE" if categoria == "IMPORTANTE" else "", "🔔")
        print("📅 Fecha:", fecha)
        print("🧑‍💼 De:", de)
        print("✉️ Asunto:", asunto)
        print("-" * 50)

        if categoria == "IMPORTANTE":
            reenviar_a = os.getenv("REENVIO_A", EMAIL)
            try:
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(EMAIL, PASSWORD)
                reenviado = MIMEText(f"Correo importante reenviado automáticamente:\n\nAsunto: {asunto}\nDe: {de}\n\n{cuerpo}")
                reenviado["Subject"] = f"[REENVÍO] {asunto}"
                reenviado["From"] = EMAIL
                reenviado["To"] = reenviar_a
                server.sendmail(EMAIL, reenviar_a, reenviado.as_string())
                server.quit()
                print(f"📬 Correo reenviado automáticamente a: {reenviar_a}")
            except Exception as e:
                print(f"❌ Error al reenviar: {e}")

            enviar_whatsapp(asunto, de, categoria)

        enviar_respuesta(correo_remitente)
        guardar_registro(fecha, de, asunto, categoria, True)

    mail.logout()

if __name__ == "__main__":
    leer_correos()
