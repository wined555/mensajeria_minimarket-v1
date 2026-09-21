import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Tuple

# Configuración básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SMTPManager:
    """
    Clase para gestionar la conexión SMTP y el envío de correos electrónicos
    para el sistema de mensajería del minimarket.
    """
    
    def __init__(self, email: str, password: str, host: str, puerto: int = 587, use_tls: bool = True):
        """
        Inicializa las credenciales y configuración del servidor SMTP.
        
        :param email: Correo del remitente.
        :param password: Contraseña del correo o contraseña de aplicación (e.g. Gmail App Password).
        :param host: Servidor SMTP (e.g. smtp.gmail.com, smtp.office365.com).
        :param puerto: Puerto del servidor (587 para TLS/STARTTLS, 465 para SSL).
        :param use_tls: Si debe usar STARTTLS (por defecto True para puerto 587).
        """
        self.email = email
        self.password = password
        self.host = host
        self.puerto = puerto
        self.use_tls = use_tls

    def enviar_mensaje(self, destinatario: str, asunto: str, cuerpo: str, es_html: bool = False) -> Tuple[bool, str]:
        """
        Envía un correo electrónico y captura posibles fallos de conexión o autenticación.
        
        :param destinatario: Dirección de correo del cliente receptor.
        :param asunto: Asunto del correo.
        :param cuerpo: Contenido del mensaje (texto plano o código HTML).
        :param es_html: Indica si el cuerpo del correo debe renderizarse como HTML.
        :return: Tupla (exito: bool, estado: str) diseñada para registrar el resultado 
                 directamente en la tabla 'historial' de la base de datos.
        """
        # Preparar estructura del correo
        msg = MIMEMultipart()
        msg['From'] = self.email
        msg['To'] = destinatario
        msg['Subject'] = Header(asunto, 'utf-8')

        # Adjuntar cuerpo según formato
        subtipo = 'html' if es_html else 'plain'
        msg.attach(MIMEText(cuerpo, subtipo, 'utf-8'))

        server = None
        try:
            logging.info(f"Conectando al servidor SMTP {self.host}:{self.puerto}...")
            
            # Conexión SSL directa (puerto 465) o estándar/STARTTLS (puerto 587 u otros)
            if self.puerto == 465 and not self.use_tls:
                server = smtplib.SMTP_SSL(self.host, self.puerto, timeout=15)
            else:
                server = smtplib.SMTP(self.host, self.puerto, timeout=15)
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                    server.ehlo()

            # Autenticación
            server.login(self.email, self.password)

            # Envío del mensaje
            server.send_message(msg)

            estado = "Enviado"
            logging.info(f"Mensaje enviado con éxito a {destinatario}.")
            return True, estado

        except smtplib.SMTPAuthenticationError as e:
            detalle = e.smtp_error.decode(errors="ignore") if isinstance(e.smtp_error, bytes) else str(e)
            estado = f"Fallo: Error de autenticación ({detalle})"
            logging.error(f"Fallo de autenticación para {self.email}: {estado}")
            return False, estado

        except smtplib.SMTPConnectError as e:
            estado = f"Fallo: No se pudo conectar al servidor {self.host}:{self.puerto}"
            logging.error(f"Error de conexión SMTP: {e}")
            return False, estado

        except smtplib.SMTPServerDisconnected as e:
            estado = "Fallo: El servidor SMTP se desconectó inesperadamente"
            logging.error(f"Desconexión de servidor: {e}")
            return False, estado

        except smtplib.SMTPRecipientsRefused:
            estado = f"Fallo: El destinatario fue rechazado ({destinatario})"
            logging.error(estado)
            return False, estado

        except smtplib.SMTPException as e:
            estado = f"Fallo SMTP: {str(e)}"
            logging.error(f"Error general SMTP al enviar a {destinatario}: {e}")
            return False, estado

        except TimeoutError:
            estado = f"Fallo: Tiempo de espera agotado al conectar con {self.host}:{self.puerto}"
            logging.error(estado)
            return False, estado

        except Exception as e:
            estado = f"Fallo inesperado: {str(e)}"
            logging.error(f"Excepción no controlada: {e}")
            return False, estado

        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    def verificar_conexion(self) -> Tuple[bool, str]:
        """
        Verifica la conexión y autenticación con el servidor SMTP sin enviar ningún mensaje.
        
        :return: Tupla (exito: bool, mensaje: str)
        """
        server = None
        try:
            logging.info(f"Comprobando conexión con servidor SMTP {self.host}:{self.puerto}...")
            if self.puerto == 465 and not self.use_tls:
                server = smtplib.SMTP_SSL(self.host, self.puerto, timeout=12)
            else:
                server = smtplib.SMTP(self.host, self.puerto, timeout=12)
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                    server.ehlo()

            # Autenticación
            server.login(self.email, self.password)
            logging.info(f"Autenticación SMTP exitosa para {self.email}.")
            return True, "Conexión y autenticación SMTP exitosa."

        except smtplib.SMTPAuthenticationError as e:
            detalle = e.smtp_error.decode(errors="ignore") if isinstance(e.smtp_error, bytes) else str(e)
            msg = f"Error de autenticación: Verifique su correo o contraseña de aplicación ({detalle})"
            logging.error(f"Fallo de autenticación SMTP para {self.email}: {msg}")
            return False, msg

        except smtplib.SMTPConnectError as e:
            msg = f"No se pudo conectar al servidor SMTP {self.host}:{self.puerto}."
            logging.error(f"Error de conexión SMTP: {e}")
            return False, msg

        except smtplib.SMTPServerDisconnected as e:
            msg = "El servidor SMTP se desconectó inesperadamente."
            logging.error(f"Desconexión SMTP: {e}")
            return False, msg

        except TimeoutError:
            msg = f"Tiempo de espera agotado al conectar con {self.host}:{self.puerto}."
            logging.error(msg)
            return False, msg

        except smtplib.SMTPException as e:
            msg = f"Error SMTP: {str(e)}"
            logging.error(msg)
            return False, msg

        except Exception as e:
            msg = f"Error inesperado al verificar SMTP: {str(e)}"
            logging.error(msg)
            return False, msg

        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass


# ==========================================
# Ejemplo de uso e integración con database.py
# ==========================================
if __name__ == "__main__":
    print("=== Prueba de inicialización de SMTPManager ===")
    # Credenciales de ejemplo (se deben sustituir por datos reales o variables de entorno)
    smtp = SMTPManager(
        email="ejemplo@minimarket.com",
        password="password_o_token",
        host="smtp.gmail.com",
        puerto=587
    )

    print("Intentando enviar un correo con credenciales de prueba...")
    # Intentamos enviar un correo; fallará la autenticación de forma controlada
    exito, estado = smtp.enviar_mensaje(
        destinatario="cliente@example.com",
        asunto="¡Oferta especial en Minimarket!",
        cuerpo="Hola, te informamos de nuestras nuevas promociones en el minimarket."
    )

    print(f"Resultado del envío:")
    print(f" - Éxito: {exito}")
    print(f" - Estado para DB: {estado}")
