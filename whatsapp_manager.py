import os
import re
import io
import time
import base64
import shutil
import logging
import threading
import subprocess
import socket
from typing import Tuple, Optional, Callable

import qrcode
from PIL import Image

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
    SessionNotCreatedException
)
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

# Configurar registro de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def formatear_telefono_internacional(numero_raw: str) -> str:
    """Formatea un número de WhatsApp con su prefijo internacional legible (ej: 59172465746 -> +591 72465746)."""
    if not numero_raw:
        return ""
    digits = re.sub(r'\D', '', str(numero_raw))
    if not digits:
        return ""
    prefijos = [
        ("591", 8),   # Bolivia (+591 XXXXXXXX)
        ("51", 9),    # Perú (+51 XXXXXXXXX)
        ("54", 10),   # Argentina
        ("56", 9),    # Chile
        ("57", 10),   # Colombia
        ("593", 9),   # Ecuador
        ("595", 9),   # Paraguay
        ("598", 8),   # Uruguay
        ("55", 11),   # Brasil
        ("52", 10),   # México
        ("34", 9),    # España
        ("1", 10),    # USA / Canadá
    ]
    for pref, _ in prefijos:
        if digits.startswith(pref) and len(digits) > len(pref):
            resto = digits[len(pref):]
            return f"+{pref} {resto}"
    return f"+{digits}"


class GestorWhatsApp:
    """
    Gestor de automatización para WhatsApp Web mediante Selenium WebDriver y CDP.
    Ejecuta el navegador de forma nativa en segundo plano (--headless=new) y mantiene
    la sesión del usuario persistente de forma segura y compatible con antivirus.
    """

    # Selectores XPath robustos para WhatsApp Web
    XPATH_INPUT_BOX = (
        "//footer//div[@contenteditable='true'] | "
        "//div[@id='main']//footer//div[@contenteditable='true'] | "
        "//div[@id='main']//div[@contenteditable='true'][@data-tab='10']"
    )
    
    XPATH_SEND_BUTTON = (
        "//footer//button[@data-testid='send'] | "
        "//footer//button[@data-testid='compose-btn-send'] | "
        "//footer//span[@data-icon='send']/ancestor::button | "
        "//footer//button[.//span[@data-icon='send']] | "
        "//footer//button[@aria-label='Enviar'] | "
        "//footer//button[@aria-label='Send']"
    )
    
    XPATH_POPUP_INVALIDO = (
        "//div[contains(text(), 'no es válido') or "
        "contains(text(), 'invalid') or "
        "contains(text(), 'no es valido') or "
        "contains(text(), 'El número de teléfono')] | "
        "//div[@data-animate-modal-popup='true'] | "
        "//div[@role='alert']"
    )

    DEFAULT_DATA_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "MinimarketSuite",
        "whatsapp_cdp_profile"
    )

    def __init__(self, user_data_dir: Optional[str] = None, navegador: str = "chrome", headless: bool = True):
        """
        Inicializa el navegador configurando un 'user data dir' persistente para guardar la sesión
        y ejecutándolo de forma 100% oculta en segundo plano mediante --headless=new.
        """
        self._lock = threading.RLock()
        if not user_data_dir or user_data_dir.strip() in ("whatsapp_profile", "whatsapp_session", "whatsapp_cdp_profile"):
            self.user_data_dir = os.path.abspath(self.DEFAULT_DATA_DIR)
        else:
            self.user_data_dir = os.path.abspath(user_data_dir)

        self.navegador = navegador.lower().strip()
        self.headless = headless
        self.driver: Optional[webdriver.Remote] = None
        self.browser_process: Optional[subprocess.Popen] = None
        self.cdp_port: int = self._obtener_puerto_cdp_libre()
        self._cuenta_conectada: dict = {
            "conectado": False,
            "telefono": "",
            "telefono_formateado": "",
            "nombre": "",
            "wid": ""
        }

        # Limpiar procesos huérfanos antes de iniciar
        self._matar_procesos_huerfanos()

        try:
            self._iniciar_navegador()
        except (SessionNotCreatedException, WebDriverException) as e:
            logging.warning(f"Error al iniciar navegador en primer intento ({e}). Reintentando tras matar procesos huérfanos...")
            self._matar_procesos_huerfanos()
            time.sleep(1)
            self.cdp_port = self._obtener_puerto_cdp_libre()
            self._iniciar_navegador()

    def _obtener_puerto_cdp_libre(self, puerto_base: int = 19890) -> int:
        """Obtiene un puerto TCP libre fuera de los rangos de exclusión de Windows (Hyper-V/WinNAT)."""
        for p in [puerto_base, puerto_base + 1, puerto_base + 2, 29890, 39890, 49890]:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(('127.0.0.1', p))
                s.close()
                return p
            except OSError:
                continue
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('127.0.0.1', 0))
            p = s.getsockname()[1]
            s.close()
            return p
        except Exception:
            return 19890

    def _matar_procesos_huerfanos(self):
        """Termina procesos huérfanos de Chrome o ChromeDriver asociados al minimarket o puerto CDP."""
        if self.browser_process:
            try:
                self.browser_process.terminate()
                self.browser_process.kill()
            except Exception:
                pass
            self.browser_process = None

        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info['name'] or '').lower()
                    if 'chromedriver' in name:
                        proc.kill()
                    elif 'chrome' in name or 'msedge' in name:
                        cmd = ' '.join(proc.info['cmdline'] or [])
                        if 'whatsapp_cdp_profile' in cmd or str(self.cdp_port) in cmd:
                            proc.kill()
                except Exception:
                    pass
        except Exception:
            pass

    def _limpiar_directorio_perfil(self):
        """Elimina el directorio de perfil para limpiar datos corruptos si fuera necesario."""
        self.cerrar()
        self._matar_procesos_huerfanos()

        if os.path.exists(self.user_data_dir):
            try:
                time.sleep(0.8)
                shutil.rmtree(self.user_data_dir, ignore_errors=True)
                logging.info(f"Carpeta de perfil '{self.user_data_dir}' eliminada con éxito.")
            except Exception as err:
                logging.error(f"Error al eliminar la carpeta de perfil: {err}")

    def _buscar_ejecutable_navegador(self) -> Optional[str]:
        """Localiza de forma automática el ejecutable del navegador en el sistema."""
        candidatos = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        for c in candidatos:
            if os.path.isfile(c):
                return c
        return None

    def _iniciar_navegador(self):
        """
        Arranca el navegador mediante arquitectura CDP (Chrome DevTools Protocol).
        El proceso del navegador se ejecuta directamente como aplicación de confianza de Windows,
        evitando bloqueos de lectura en 'Preferences' provocados por antivirus (como ESET),
        y Selenium se conecta a él a través del puerto de depuración.
        """
        logging.info(f"Iniciando navegador ({self.navegador}) [Headless={self.headless}] con User Data Dir en: {self.user_data_dir}")
        os.makedirs(self.user_data_dir, exist_ok=True)

        ejecutable = self._buscar_ejecutable_navegador()
        if ejecutable:
            try:
                cmd = [
                    ejecutable,
                    f"--user-data-dir={self.user_data_dir}",
                    f"--remote-debugging-port={self.cdp_port}",
                    "--remote-allow-origins=*",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ]
                if self.headless:
                    cmd.append("--headless=new")
                    cmd.append("--window-size=1920,1080")
                else:
                    cmd.append("--start-maximized")

                cmd.append("https://web.whatsapp.com")

                logging.info(f"Lanzando proceso nativo: {ejecutable} en puerto CDP {self.cdp_port}...")
                self.browser_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                from selenium.webdriver.chrome.options import Options as ChromeOptions
                options = ChromeOptions()
                options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.cdp_port}")

                driver_path = ChromeDriverManager().install()
                service = ChromeService(driver_path)

                conectado = False
                for _ in range(12):
                    time.sleep(0.5)
                    try:
                        self.driver = webdriver.Chrome(service=service, options=options)
                        conectado = True
                        break
                    except Exception:
                        pass

                if conectado and self.driver:
                    try:
                        self.driver.set_page_load_timeout(25)
                        self.driver.set_script_timeout(15)
                    except Exception:
                        pass
                    logging.info("Navegador conectado exitosamente vía CDP.")
                    return
                else:
                    logging.warning("Conexión CDP agotó reintentos. Terminando proceso nativo antes de fallback...")
                    if self.browser_process:
                        try:
                            self.browser_process.terminate()
                            self.browser_process.kill()
                        except Exception:
                            pass
                        self.browser_process = None
            except Exception as e_cdp:
                logging.warning(f"Fallo al iniciar vía CDP: {e_cdp}. Terminando proceso antes de fallback...")
                if self.browser_process:
                    try:
                        self.browser_process.terminate()
                        self.browser_process.kill()
                    except Exception:
                        pass
                    self.browser_process = None

        # Fallback tradicional con ChromeDriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        options = ChromeOptions()
        options.page_load_strategy = "eager"
        options.add_argument(f"--user-data-dir={self.user_data_dir}")
        options.add_argument("--disable-extensions")
        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])

        driver_path = ChromeDriverManager().install()
        service = ChromeService(driver_path)
        self.driver = webdriver.Chrome(service=service, options=options)

        try:
            self.driver.set_page_load_timeout(25)
            self.driver.set_script_timeout(15)
        except Exception:
            pass

        if not self.headless:
            self.driver.maximize_window()

        logging.info("Navegador inicializado correctamente en modo estándar.")

    def verificar_sesion_activa(self, forzar_navegacion: bool = False, timeout_espera: int = 8) -> bool:
        """
        Comprueba de forma precisa y segura si WhatsApp Web tiene una sesión activa iniciada.
        Espera hasta timeout_espera segundos contemplando la sincronización de mensajes desde IndexedDB.
        """
        with self._lock:
            if not self.driver:
                return False
            try:
                current_url = ""
                try:
                    current_url = self.driver.current_url
                except Exception:
                    pass

                if "web.whatsapp.com" not in current_url:
                    if forzar_navegacion:
                        self.driver.get("https://web.whatsapp.com")
                        time.sleep(1.5)
                    else:
                        return False

                inicio = time.time()
                while (time.time() - inicio) < max(1, timeout_espera):
                    res = self.driver.execute_script("""
                        const hasPane = !!document.querySelector('#pane-side') || 
                                        !!document.querySelector('#side') ||
                                        !!document.querySelector('[data-testid="chat-list"]') ||
                                        !!document.querySelector('[data-testid="chatlist-header"]') ||
                                        !!document.querySelector("header [data-icon='chat']") ||
                                        !!document.querySelector("header [data-icon='menu']") ||
                                        !!document.querySelector("header [data-icon='status-outline']") ||
                                        !!document.querySelector("header [data-icon='newsletter-outline']") ||
                                        !!document.querySelector("[data-tab='2']") ||
                                        !!document.querySelector("[data-tab='3']") ||
                                        !!document.querySelector("span[data-icon='chats']");
                        const hasQR = !!document.querySelector('canvas') || !!document.querySelector('[data-ref]');
                        const isProgress = !!document.querySelector('progress, [role="progressbar"]') || 
                                           (document.body && (document.body.innerText.includes('descargando tus mensajes') || 
                                                              document.body.innerText.includes('Cargando tus chats')));
                        return { hasPane, hasQR, isProgress };
                    """)
                    if res and res.get("hasPane"):
                        if not self._cuenta_conectada.get("telefono"):
                            try:
                                self.obtener_datos_cuenta_conectada(forzar_refresco=False)
                            except Exception:
                                pass
                        return True

                    # Si hay código QR explícito y no está en progreso de descarga de mensajes
                    if res and res.get("hasQR") and not res.get("isProgress"):
                        return False

                    time.sleep(0.6)

                return False
            except Exception as e:
                logging.debug(f"Error verificando sesion activa: {e}")
                return False

    def cerrar_sesion_whatsapp(self) -> bool:
        """Cierra la sesión activa en WhatsApp Web para permitir vincular un nuevo número."""
        with self._lock:
            if not self.driver:
                return True
            try:
                logging.info("Intentando cerrar sesión en WhatsApp Web...")
                self.driver.execute_script("""
                    const menuBtn = document.querySelector("header [data-icon='menu']") || 
                                    document.querySelector("header div[role='button'][title*='Menú']");
                    if (menuBtn) menuBtn.click();
                """)
                time.sleep(0.5)
                self.driver.execute_script("""
                    const btns = Array.from(document.querySelectorAll("div[role='button'], li, span"));
                    const logoutBtn = btns.find(el => el.innerText && (el.innerText.toLowerCase().includes('cerrar sesión') || el.innerText.toLowerCase().includes('log out')));
                    if (logoutBtn) logoutBtn.click();
                """)
                time.sleep(1)
                self.driver.execute_script("""
                    const confirmBtns = Array.from(document.querySelectorAll("button, div[role='button']"));
                    const confirm = confirmBtns.find(el => el.innerText && (el.innerText.toLowerCase().includes('cerrar sesión') || el.innerText.toLowerCase().includes('log out')));
                    if (confirm) confirm.click();
                """)
                time.sleep(1.5)
                # Forzar eliminación de perfil para limpieza absoluta
                self._cuenta_conectada = {
                    "conectado": False,
                    "telefono": "",
                    "telefono_formateado": "",
                    "nombre": "",
                    "wid": ""
                }
                self._limpiar_directorio_perfil()
                return True
            except Exception as e:
                logging.warning(f"Error al cerrar sesion en WhatsApp Web: {e}")
                self._cuenta_conectada = {
                    "conectado": False,
                    "telefono": "",
                    "telefono_formateado": "",
                    "nombre": "",
                    "wid": ""
                }
                self._limpiar_directorio_perfil()
                return False

    def obtener_datos_cuenta_conectada(self, forzar_refresco: bool = False) -> dict:
        """
        Extrae y retorna de forma segura y no intrusiva la información de la cuenta
        de WhatsApp Web actualmente conectada:
        - telefono: solo dígitos (ej. "59172465746")
        - telefono_formateado: formato con prefijo (ej. "+591 72465746")
        - nombre: nombre de perfil / pushname (ej. "Minimarket Los Andes")
        - wid: JID completo en WhatsApp (ej. "59172465746@c.us")
        - conectado: bool
        """
        with self._lock:
            # Si ya tenemos datos en caché válidos y no se pide forzar refresco, retornar caché
            if not forzar_refresco and self._cuenta_conectada.get("conectado") and self._cuenta_conectada.get("telefono"):
                return dict(self._cuenta_conectada)

            if not self.driver:
                return {
                    "conectado": False,
                    "telefono": "",
                    "telefono_formateado": "",
                    "nombre": "",
                    "wid": ""
                }

            try:
                datos = self.driver.execute_script("""
                    let telefono = "";
                    let nombre = "";
                    let wid = "";

                    // 1. Extraer WID y teléfono desde localStorage
                    try {
                        const lastWidMd = localStorage.getItem('last-wid-md');
                        if (lastWidMd) {
                            wid = lastWidMd.replace(/["']/g, '').trim();
                        }
                    } catch(e) {}

                    if (!wid) {
                        try {
                            const lastWid = localStorage.getItem('last-wid');
                            if (lastWid) wid = lastWid.replace(/["']/g, '').trim();
                        } catch(e) {}
                    }

                    // Si aún no se encontró, escanear claves en localStorage con patrón JID
                    if (!wid) {
                        try {
                            for (let i = 0; i < localStorage.length; i++) {
                                const k = localStorage.key(i);
                                const val = localStorage.getItem(k);
                                if (val && typeof val === 'string') {
                                    const m = val.match(/["']?(\\d{7,15})(?::\\d+)?@c\\.us["']?/);
                                    if (m) {
                                        wid = m[1] + '@c.us';
                                        telefono = m[1];
                                        break;
                                    }
                                }
                            }
                        } catch(e) {}
                    }

                    if (wid && !telefono) {
                        const m = wid.match(/^(\\d{7,15})/) || wid.match(/(\\d{7,15})/);
                        if (m) telefono = m[1];
                    }

                    // 2. Extraer nombre de perfil (pushname) desde localStorage
                    try {
                        const pn = localStorage.getItem('pushname');
                        if (pn && pn.trim() && pn !== 'undefined' && pn !== 'null') {
                            nombre = pn.replace(/["']/g, '').trim();
                        }
                    } catch(e) {}

                    if (!nombre) {
                        try {
                            for (const key of ['user-name', 'profile_name', 'wa-user-name', 'me_name', 'username']) {
                                const val = localStorage.getItem(key);
                                if (val && val.trim() && val !== 'undefined' && val !== 'null') {
                                    nombre = val.replace(/["']/g, '').trim();
                                    break;
                                }
                            }
                        } catch(e) {}
                    }

                    // 3. Comprobación vía Store interno si estuviese disponible
                    try {
                        if (window.Store) {
                            if (window.Store.Conn) {
                                if (!telefono && window.Store.Conn.wid) {
                                    telefono = window.Store.Conn.wid.user || "";
                                }
                                if (!nombre && window.Store.Conn.pushname) {
                                    nombre = window.Store.Conn.pushname.trim();
                                }
                            }
                            if (!telefono && window.Store.User && window.Store.User.getMeUser) {
                                const me = window.Store.User.getMeUser();
                                if (me && me.user) telefono = me.user;
                            }
                        }
                    } catch(e) {}

                    // 4. Fallback a atributos de imagen del header del avatar
                    try {
                        if (!nombre) {
                            const avatarImg = document.querySelector("header img[alt]");
                            if (avatarImg) {
                                let alt = (avatarImg.getAttribute('alt') || '').trim();
                                const mAlt = alt.match(/(?:foto\\s+d?e?l?\\s*perfil\\s+de|profile\\s+photo\\s+of)\\s+(.+)/i);
                                if (mAlt && mAlt[1]) {
                                    nombre = mAlt[1].trim();
                                } else if (alt && !alt.toLowerCase().includes('avatar') && !alt.toLowerCase().includes('perfil') && !alt.toLowerCase().includes('foto')) {
                                    nombre = alt;
                                }
                            }
                        }
                    } catch(e) {}

                    // 5. Fallback a atributos title en el botón de perfil del header
                    try {
                        if (!nombre) {
                            const btnProfile = document.querySelector("header div[role='button'][title]");
                            if (btnProfile) {
                                let t = (btnProfile.getAttribute('title') || '').trim();
                                if (t && !t.toLowerCase().includes('perfil') && !t.toLowerCase().includes('profile') && !t.toLowerCase().includes('menú') && !t.toLowerCase().includes('menu')) {
                                    nombre = t;
                                }
                            }
                        }
                    } catch(e) {}

                    return {
                        telefono: telefono || "",
                        nombre: nombre || "",
                        wid: wid || ""
                    };
                """) or {}

                telefono_raw = (datos.get("telefono") or "").strip()
                nombre_raw = (datos.get("nombre") or "").strip()
                wid_raw = (datos.get("wid") or "").strip()

                telefono_clean = re.sub(r'\D', '', telefono_raw)
                tel_formateado = formatear_telefono_internacional(telefono_clean) if telefono_clean else ""
                esta_conectado = bool(telefono_clean or wid_raw)

                self._cuenta_conectada = {
                    "conectado": esta_conectado,
                    "telefono": telefono_clean,
                    "telefono_formateado": tel_formateado,
                    "nombre": nombre_raw,
                    "wid": wid_raw
                }
                return dict(self._cuenta_conectada)
            except Exception as e:
                logging.debug(f"Error extrayendo datos de cuenta WhatsApp: {e}")
                return {
                    "conectado": False,
                    "telefono": "",
                    "telefono_formateado": "",
                    "nombre": "",
                    "wid": ""
                }

    def _intentar_click_recargar_qr(self) -> bool:
        """Intenta hacer clic en el botón nativo de recarga de QR si ha expirado."""
        if not self.driver:
            return False
        try:
            clicado = self.driver.execute_script("""
                const btn = document.querySelector("[data-icon='refresh']") || 
                            document.querySelector("[data-icon='refresh-large']") ||
                            document.querySelector("button[aria-label*='recargar']") ||
                            document.querySelector("button[aria-label*='reload']") ||
                            document.querySelector("[data-testid='reload-qr']");
                if (btn) {
                    const clickable = btn.closest("button") || btn.closest("div[role='button']") || btn;
                    clickable.click();
                    return true;
                }
                const qrContainer = document.querySelector("[data-testid='link-device-qr-code']");
                if (qrContainer) {
                    const overlayBtn = qrContainer.querySelector("button, div[role='button']");
                    if (overlayBtn) {
                        overlayBtn.click();
                        return true;
                    }
                }
                return false;
            """)
            if clicado:
                logging.info("Botón nativo de recarga de QR pulsado exitosamente.")
                time.sleep(1)
                return True
        except Exception as e:
            logging.debug(f"No se pudo hacer clic en botón de recarga: {e}")
        return False

    def obtener_qr_base64(self, timeout: int = 35) -> Optional[str]:
        """
        Obtiene el código QR de vinculación de WhatsApp Web.
        
        - Si la sesión ya está iniciada, retorna 'CONECTADO'.
        - Extrae el token 'data-ref' directamente del DOM y genera una imagen QR nítida
          de alta resolución con la librería 'qrcode' (con margen blanco 'quiet zone'
          reglamentario para que cualquier celular lo reconozca al instante).
        - Si no encuentra 'data-ref', recurre al screenshot del <canvas> añadiéndole
          un borde blanco protector para compatibilidad total con el modo oscuro.
        - En recargas sucesivas, pulsa el botón nativo de refresco en milisegundos
          sin recargar la página completa, evitando cuelgues.
        """
        with self._lock:
            if not self.driver:
                self._iniciar_navegador()

            try:
                # 1. Verificar si ya se encuentra conectado
                if self.verificar_sesion_activa():
                    logging.info("La sesión de WhatsApp ya se encuentra iniciada en este equipo.")
                    return "CONECTADO"

                # 2. Navegar o refrescar según corresponda
                current_url = ""
                try:
                    current_url = self.driver.current_url
                except Exception:
                    pass

                ya_en_whatsapp = "web.whatsapp.com" in current_url
                if not ya_en_whatsapp:
                    logging.info("Navegando a https://web.whatsapp.com para capturar código QR...")
                    self.driver.get("https://web.whatsapp.com")
                else:
                    logging.info("Ya en WhatsApp Web. Comprobando botón de recarga nativo...")
                    self._intentar_click_recargar_qr()

                tiempo_inicio = time.time()
                while (time.time() - tiempo_inicio) < timeout:
                    # Comprobar si se inició sesión
                    if self.verificar_sesion_activa():
                        logging.info("Sesión iniciada detectada.")
                        return "CONECTADO"

                    # Intentar extraer el token data-ref (Método de máxima calidad)
                    data_ref = None
                    try:
                        data_ref = self.driver.execute_script(
                            "return document.querySelector('[data-ref]')?.getAttribute('data-ref') || null;"
                        )
                    except Exception:
                        pass

                    if data_ref and len(data_ref.strip()) > 10:
                        logging.info(f"Token data-ref detectado ({len(data_ref)} caracteres). Generando QR de alta definición...")
                        try:
                            qr = qrcode.QRCode(
                                version=None,
                                error_correction=qrcode.constants.ERROR_CORRECT_M,
                                box_size=8,
                                border=4,
                            )
                            qr.add_data(data_ref.strip())
                            qr.make(fit=True)
                            pil_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

                            buf = io.BytesIO()
                            pil_img.save(buf, format="PNG")
                            qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                            logging.info("Código QR HD generado con éxito (con margen blanco reglamentario).")
                            return qr_b64
                        except Exception as e_qr:
                            logging.warning(f"Error generando con 'qrcode': {e_qr}. Intentando fallback canvas.")

                    # Método Fallback: Elemento <canvas> con margen blanco de seguridad
                    canvas_list = self.driver.find_elements(By.XPATH, "//canvas")
                    if canvas_list and canvas_list[0].is_displayed():
                        canvas = canvas_list[0]
                        try:
                            raw_b64 = canvas.screenshot_as_base64
                            if raw_b64:
                                img_raw = Image.open(io.BytesIO(base64.b64decode(raw_b64))).convert("RGB")
                                w, h = img_raw.size
                                padding = 24
                                padded_img = Image.new("RGB", (w + padding * 2, h + padding * 2), (255, 255, 255))
                                padded_img.paste(img_raw, (padding, padding))

                                buf = io.BytesIO()
                                padded_img.save(buf, format="PNG")
                                qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                                logging.info("Código QR extraído vía canvas con margen de seguridad blanco.")
                                return qr_b64
                        except Exception as e_shot:
                            logging.warning(f"screenshot_as_base64 falló: {e_shot}")

                    # Si el QR expiró, pulsar botón de recarga
                    self._intentar_click_recargar_qr()

                    time.sleep(1)

                logging.warning("Tiempo de espera agotado buscando código QR en WhatsApp Web.")
                return None

            except Exception as e:
                logging.error(f"Error al obtener QR en base64: {e}")
                raise

    def _limpiar_numero(self, numero: str) -> str:
        """Remueve cualquier caracter que no sea dígito."""
        return re.sub(r'\D', '', str(numero))

    def _verificar_conexion_internet(self) -> bool:
        """Verifica si el navegador tiene acceso a la red."""
        try:
            return bool(self.driver.execute_script("return navigator.onLine;"))
        except Exception:
            return True

    def enviar_mensaje_whatsapp(
        self, 
        numero: str, 
        mensaje: str, 
        timeout: int = 22,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> Tuple[bool, str]:
        """
        Abre directamente el chat del número en WhatsApp Web con el texto pre-cargado,
        espera a que cargue el cuadro de texto en el pie de página (footer), envía el mensaje y verifica.

        :param numero: Número de teléfono (si es de 8 dígitos de Bolivia, antepone automáticamente 591).
        :param mensaje: Texto del mensaje a enviar.
        :param timeout: Tiempo máximo en segundos para esperar la carga de los elementos.
        :param cancel_check: Función que retorna True si la cola fue cancelada por el usuario.
        :return: Tupla (exito: bool, estado: str) para registrar en historial o base de datos.
        """
        if not self.driver:
            self._iniciar_navegador()

        # 1. Validar conexión a Internet
        if not self._verificar_conexion_internet():
            estado = "Fallo: No hay conexión a Internet en el equipo."
            logging.error(estado)
            return False, estado

        # 2. Sanitizar número telefónico
        numero_limpio = self._limpiar_numero(numero)
        if len(numero_limpio) < 7:
            estado = f"Fallo: El número '{numero}' es inválido o demasiado corto."
            logging.error(estado)
            return False, estado

        # Si es un número boliviano de 8 dígitos sin prefijo (ej: 67220995 o 7xxxxxxx), anteponer 591
        if len(numero_limpio) == 8 and numero_limpio[0] in ('6', '7'):
            numero_limpio = f"591{numero_limpio}"
            logging.info(f"Número de 8 dígitos detectado (Bolivia). Auto-completando a: {numero_limpio}")

        if not mensaje or not mensaje.strip():
            return False, "Fallo: El mensaje no puede estar vacío."

        try:
            import urllib.parse
            # 3. Navegar directamente a WhatsApp Web con el número y texto pre-cargado
            url_wsp = f"https://web.whatsapp.com/send?phone={numero_limpio}&text={urllib.parse.quote(mensaje)}"
            logging.info(f"Navegando a chat de WhatsApp Web para {numero_limpio}...")
            self.driver.get(url_wsp)

            # 4. Esperar carga del chat o detectar alerta de número inválido
            tiempo_inicio = time.time()
            enviado = False

            while (time.time() - tiempo_inicio) < timeout:
                # Comprobar cancelación inmediata por parte del usuario
                if cancel_check and cancel_check():
                    logging.info("Envío cancelado por el usuario mediante cancel_check.")
                    return False, "Envío cancelado por el usuario."

                # Detección temprana: si WhatsApp redirecciona al QR, la sesión no está activa
                qr_detectado = self.driver.execute_script("""
                    return !!document.querySelector('canvas') || !!document.querySelector('[data-ref]');
                """)
                if qr_detectado:
                    estado = "Fallo: WhatsApp Web desvinculado (requiere escanear código QR)."
                    logging.warning(estado)
                    return False, estado

                # Comprobar si WhatsApp muestra popup de número no válido
                popup_invalido = self.driver.execute_script("""
                    const popups = document.querySelectorAll("div[data-animate-modal-popup='true'], div[role='alert'], div[data-testid='confirm-popup']");
                    for (const p of popups) {
                        const txt = (p.innerText || '').toLowerCase();
                        if (txt.includes('no es válido') || txt.includes('invalid') || txt.includes('no es valido')) {
                            const btnOk = p.querySelector("button, div[role='button']");
                            if (btnOk) btnOk.click();
                            return true;
                        }
                    }
                    return false;
                """)
                if popup_invalido:
                    estado = f"Fallo: El número +{numero_limpio} no está registrado en WhatsApp o es inválido."
                    logging.warning(estado)
                    return False, estado

                # Inspeccionar el footer: Verificar si el botón de enviar o el input del footer están disponibles
                res_footer = self.driver.execute_script("""
                    const footer = document.querySelector('footer');
                    if (!footer) return { ready: false };

                    const sendBtn = footer.querySelector(
                        'button span[data-icon="send"], span[data-icon="send"], button[data-testid="send"], button[data-testid="compose-btn-send"], button[aria-label*="Enviar"], button[aria-label*="Send"]'
                    );
                    const input = footer.querySelector('div[contenteditable="true"]');

                    if (sendBtn) {
                        const clickable = sendBtn.closest('button') || sendBtn;
                        clickable.click();
                        return { ready: true, clicked: true };
                    }
                    return { ready: !!input, hasInput: !!input, hasText: input ? !!input.innerText.trim() : false };
                """)

                if res_footer and res_footer.get("clicked"):
                    logging.info("Botón de envío en footer pulsado exitosamente.")
                    enviado = True
                    break

                # Si el input en el footer ya tiene el texto cargado pero aún no se pulsó el botón, enviar con ENTER
                if res_footer and res_footer.get("hasText"):
                    time.sleep(0.5)
                    try:
                        elementos = self.driver.find_elements(By.XPATH, "//footer//div[@contenteditable='true']")
                        if elementos and elementos[0].is_displayed():
                            elementos[0].send_keys(Keys.ENTER)
                            logging.info("Mensaje despachado mediante Keys.ENTER en el footer.")
                            enviado = True
                            break
                    except Exception:
                        pass

                time.sleep(0.8)

            if not enviado:
                estado = f"Fallo: Tiempo de espera agotado al cargar el chat de +{numero_limpio} (posible lentitud de red o sesión desvinculada)."
                logging.error(estado)
                return False, estado

            # Pausa breve de salida verificando si el usuario canceló
            for _ in range(12):
                if cancel_check and cancel_check():
                    return False, "Envío cancelado tras despacho."
                time.sleep(0.25)

            estado = f"Enviado con éxito por WhatsApp a +{numero_limpio}"
            logging.info(f"Mensaje despachado y enviado correctamente a +{numero_limpio}")
            return True, estado

        except TimeoutException:
            estado = f"Fallo: Tiempo de espera agotado al enviar mensaje a {numero_limpio}."
            logging.error(estado)
            return False, estado

        except WebDriverException as e:
            if "net::ERR_INTERNET_DISCONNECTED" in str(e) or "ERR_NAME_NOT_RESOLVED" in str(e):
                estado = "Fallo: Sin conexión a Internet."
            else:
                estado = f"Fallo de WebDriver: {str(e)[:120]}"
            logging.error(estado)
            return False, estado

        except Exception as e:
            estado = f"Fallo inesperado: {str(e)}"
            logging.error(estado)
            return False, estado

    def cerrar(self):
        """Cierra el navegador y libera los recursos del WebDriver y del proceso nativo."""
        with self._lock:
            self._cuenta_conectada = {
                "conectado": False,
                "telefono": "",
                "telefono_formateado": "",
                "nombre": "",
                "wid": ""
            }
            if self.driver:
                try:
                    self.driver.quit()
                    logging.info("WebDriver cerrado correctamente.")
                except Exception as e:
                    logging.warning(f"Error al cerrar WebDriver: {e}")
                finally:
                    self.driver = None

            if self.browser_process:
                try:
                    self.browser_process.terminate()
                    self.browser_process.wait(timeout=2)
                except Exception:
                    try:
                        self.browser_process.kill()
                    except Exception:
                        pass
                finally:
                    self.browser_process = None

