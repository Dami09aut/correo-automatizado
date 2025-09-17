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
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL, PASSWORD)
        msg = MIMEText("Gracias por tu mensaje. Hemos recibido tu correo y te responderemos pronto.")
        msg["Subject"] = "Re: Respuesta automática"
        msg["From"] = EMAIL
        msg["To"] = destinatario
        server.sendmail(EMAIL, destinatario, msg.as_string())
        server.quit()
        print("📤 Respuesta automática enviada.")
    except Exception as e:
        print(f"❌ Error al enviar respuesta automática: {e}")

def enviar_whatsapp(asunto, de, categoria):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        mensaje = client.messages.create(
            from_=TWILIO_FROM,
            to=TWILIO_TO,
            body=f"📧 Nuevo correo IMPORTANTE
De: {de}
Asunto: {asunto}
Categoría: {categoria}"
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

        de = msg.get("From")
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
                reenviado = MIMEText(f"Correo importante reenviado automáticamente:

Asunto: {asunto}
De: {de}

{cuerpo}")
                reenviado["Subject"] = f"[REENVÍO] {asunto}"
                reenviado["From"] = EMAIL
                reenviado["To"] = reenviar_a
                server.sendmail(EMAIL, reenviar_a, reenviado.as_string())
                server.quit()
                print(f"📬 Correo reenviado automáticamente a: {reenviar_a}")
            except Exception as e:
                print(f"❌ Error al reenviar: {e}")

            enviar_whatsapp(asunto, de, categoria)

        enviar_respuesta(de)
        guardar_registro(fecha, de, asunto, categoria, True)

    mail.logout()

if __name__ == "__main__":
    leer_correos()
