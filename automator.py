import logging
import random
import time
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
import schedule

from database import MinimarketDB
from smtp_manager import SMTPManager
from whatsapp_manager import GestorWhatsApp

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Automator:
    """
    Motor de automatizaciones para el Minimarket que utiliza 'schedule' para tareas periódicas.
    Evalúa reglas activas en la base de datos y despacha mensajes a través de SMTP o WhatsApp.
    """

    def __init__(self, db: MinimarketDB, whatsapp_profile: Optional[str] = None):
        self.db = db
        self.whatsapp_profile = whatsapp_profile
        self.whatsapp_gestor: Optional[GestorWhatsApp] = None
        self._scheduler_running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._cancelar_cola = False
        self.cola_en_ejecucion = False

    def cancelar_cola(self):
        """Detiene de inmediato la cola de envíos en curso."""
        self._cancelar_cola = True
        logging.info("Se ha solicitado cancelar la cola de automatización.")

    def obtener_gestor_whatsapp(self) -> GestorWhatsApp:
        """Instancia o reutiliza la sesión del gestor de WhatsApp."""
        if self.whatsapp_gestor is None or self.whatsapp_gestor.driver is None:
            logging.info("Instanciando GestorWhatsApp para envíos automáticos...")
            self.whatsapp_gestor = GestorWhatsApp(user_data_dir=self.whatsapp_profile)
        return self.whatsapp_gestor

    def evaluar_y_ejecutar(
        self, 
        smtp: Optional[SMTPManager] = None, 
        whatsapp: Optional[GestorWhatsApp] = None, 
        regla_id: Optional[int] = None,
        delay_min: Optional[int] = None,
        delay_max: Optional[int] = None,
        callback_progreso: Optional[Any] = None,
        cola_personalizada: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Lee las reglas activas de la base de datos o utiliza una cola personalizada de destinatarios,
        y despacha cada mensaje simulando intervalos humanos anti-baneo con variación aleatoria configurable.

        :param smtp: Instancia configurada de SMTPManager (opcional).
        :param whatsapp: Instancia opcional de GestorWhatsApp.
        :param regla_id: ID específico de regla (o None para todas las activas).
        :param delay_min: Tiempo mínimo de espera en segundos entre mensajes.
        :param delay_max: Tiempo máximo de espera en segundos entre mensajes.
        :param callback_progreso: Función de retorno para notificar progreso en tiempo real a la GUI.
        :param cola_personalizada: Lista explícita de clientes con reglas asignadas preconfigurados en la GUI.
        :return: Diccionario con estadísticas de la ejecución.
        """
        self._cancelar_cola = False
        self.cola_en_ejecucion = True

        # Obtener configuración de tiempos anti-baneo
        tiempos_cfg = self.db.obtener_tiempos_automatizacion()
        d_min = delay_min if delay_min is not None else tiempos_cfg.get("min_seg", 15)
        d_max = delay_max if delay_max is not None else tiempos_cfg.get("max_seg", 30)
        if d_min > d_max:
            d_min, d_max = d_max, d_min
        if d_min < 1:
            d_min = 1

        cola_envios: List[Dict[str, Any]] = []

        if cola_personalizada is not None:
            # Excluir de forma estricta cualquier cliente en estado Inactivo
            cola_envios = [
                item for item in cola_personalizada 
                if (item.get("cliente", {}).get("estado") or "").strip().lower() != "inactivo"
            ]
            total_reglas = len({item.get("nombre_regla") for item in cola_envios})
        else:
            if regla_id:
                regla = self.db.get_regla(regla_id)
                reglas = [regla] if regla and regla.get("activa") else []
            else:
                todas = self.db.get_all_reglas()
                reglas = [r for r in todas if r.get("activa")]

            clientes = self.db.get_all_clientes()
            total_reglas = len(reglas)

            for regla in reglas:
                nombre_regla = regla.get("nombre_regla", "Regla")
                tipo_canal = (regla.get("tipo") or "").strip().upper()
                condicion = (regla.get("condicion") or "").strip().lower()
                mensaje_plantilla = regla.get("mensaje", "")

                es_whatsapp = "WHATSAPP" in tipo_canal or "WSP" in tipo_canal
                es_smtp = "SMTP" in tipo_canal or "EMAIL" in tipo_canal or "CORREO" in tipo_canal
                if not es_whatsapp and not es_smtp:
                    es_whatsapp = True

                for cliente in clientes:
                    estado_cliente = (cliente.get("estado") or "").strip().lower()
                    # REGLA CRÍTICA: Nunca enviar a clientes inactivos
                    if estado_cliente == "inactivo":
                        continue

                    aplica = False
                    if condicion in ["todos", "*", ""]:
                        aplica = True
                    elif condicion in estado_cliente or estado_cliente == condicion:
                        aplica = True

                    if aplica:
                        nombre = cliente.get("nombre", "Estimado cliente")
                        correo = (cliente.get("correo") or "").strip()
                        telefono = (cliente.get("telefono") or "").strip()
                        estado_cli = cliente.get("estado", "")

                        cuerpo = (
                            mensaje_plantilla
                            .replace("{nombre}", nombre)
                            .replace("{correo}", correo)
                            .replace("{telefono}", telefono)
                            .replace("{estado}", estado_cli)
                        )

                        cola_envios.append({
                            "cliente": cliente,
                            "nombre": nombre,
                            "correo": correo,
                            "telefono": telefono,
                            "regla": regla,
                            "nombre_regla": nombre_regla,
                            "es_whatsapp": es_whatsapp,
                            "canal": "WhatsApp" if es_whatsapp else "SMTP",
                            "cuerpo": cuerpo
                        })

        total_items = len(cola_envios)
        resultados = {
            "total_reglas": total_reglas,
            "total_cola": total_items,
            "enviados": 0,
            "fallidos": 0,
            "cancelado": False,
            "detalles": []
        }

        if total_items == 0:
            logging.info("No hay destinatarios en cola para las reglas activas.")
            self.cola_en_ejecucion = False
            if callback_progreso:
                callback_progreso({
                    "evento": "vacio",
                    "mensaje": "No hay destinatarios que cumplan las condiciones de las reglas activas."
                })
            return resultados

        logging.info(f"Iniciando cola de envíos: {total_items} mensajes programados. Intervalo humano: {d_min}s a {d_max}s.")
        if callback_progreso:
            callback_progreso({
                "evento": "iniciado",
                "total": total_items,
                "d_min": d_min,
                "d_max": d_max
            })

        # 2. Despachar la cola secuencialmente con pausas humanas
        for idx, tarea in enumerate(cola_envios):
            if self._cancelar_cola:
                logging.info("Ejecución de cola cancelada por el usuario.")
                resultados["cancelado"] = True
                if callback_progreso:
                    callback_progreso({
                        "evento": "cancelado",
                        "indice": idx,
                        "total": total_items,
                        "enviados": resultados["enviados"],
                        "fallidos": resultados["fallidos"]
                    })
                break

            nombre = tarea["nombre"]
            canal = tarea["canal"]
            es_whatsapp = tarea["es_whatsapp"]
            cuerpo = tarea["cuerpo"]
            cliente = tarea["cliente"]
            nombre_regla = tarea["nombre_regla"]
            telefono = tarea["telefono"]
            correo = tarea["correo"]
            indice_item = tarea.get("indice_cola", idx)

            if callback_progreso:
                callback_progreso({
                    "evento": "enviando",
                    "indice": idx + 1,
                    "indice_item": indice_item,
                    "total": total_items,
                    "cliente": nombre,
                    "canal": canal,
                    "regla": nombre_regla,
                    "enviados": resultados["enviados"],
                    "fallidos": resultados["fallidos"]
                })

            if es_whatsapp:
                if not telefono:
                    estado_envio = "Fallo: Sin número telefónico registrado"
                    exito = False
                else:
                    try:
                        w_gestor = whatsapp or self.obtener_gestor_whatsapp()
                        logging.info(f"Enviando WhatsApp a {nombre} ({telefono})...")
                        exito, estado_envio = w_gestor.enviar_mensaje_whatsapp(
                            numero=telefono, 
                            mensaje=cuerpo,
                            cancel_check=lambda: self._cancelar_cola
                        )
                    except Exception as err:
                        exito = False
                        estado_envio = f"Error en WhatsApp: {err}"
            else:
                if not correo:
                    estado_envio = "Fallo: Sin correo electrónico registrado"
                    exito = False
                else:
                    if not smtp:
                        creds = self.db.obtener_credenciales_smtp()
                        if creds.get("email") and creds.get("password"):
                            smtp = SMTPManager(
                                email=creds["email"],
                                password=creds["password"],
                                host=creds.get("host", "smtp.gmail.com"),
                                puerto=creds.get("puerto", 587),
                                use_tls=creds.get("tls", True)
                            )
                    if not smtp:
                        estado_envio = "Fallo: No hay credenciales SMTP configuradas"
                        exito = False
                    else:
                        asunto = f"Aviso Minimarket: {nombre_regla}"
                        exito, estado_envio = smtp.enviar_mensaje(destinatario=correo, asunto=asunto, cuerpo=cuerpo)

            hora_envio_exacta = datetime.now().strftime("%H:%M:%S")

            # Registrar en la base de datos
            self.db.create_historial(
                cliente_id=cliente["id"],
                estado=f"Auto [{canal}-{nombre_regla}]: {estado_envio}"
            )

            if exito:
                resultados["enviados"] += 1
            else:
                resultados["fallidos"] += 1

            resultados["detalles"].append({
                "cliente": nombre,
                "canal": canal,
                "destino": telefono if es_whatsapp else correo,
                "regla": nombre_regla,
                "estado": estado_envio,
                "hora": hora_envio_exacta
            })

            if callback_progreso:
                callback_progreso({
                    "evento": "item_completado",
                    "indice": idx + 1,
                    "indice_item": indice_item,
                    "hora_envio": hora_envio_exacta,
                    "total": total_items,
                    "cliente": nombre,
                    "canal": canal,
                    "exito": exito,
                    "estado": estado_envio,
                    "enviados": resultados["enviados"],
                    "fallidos": resultados["fallidos"]
                })

            # Si no es el último mensaje y la cola sigue activa: aplicar intervalo humano anti-baneo
            if idx < total_items - 1 and not self._cancelar_cola:
                pausa_humana = round(random.uniform(d_min, d_max), 1)
                siguiente_nombre = cola_envios[idx + 1]["nombre"]
                logging.info(f"Pausa humana anti-spam: esperando {pausa_humana}s antes de enviar a {siguiente_nombre}...")

                segundos_enteros = int(pausa_humana)
                for seg_restante in range(segundos_enteros, 0, -1):
                    if self._cancelar_cola:
                        break
                    if callback_progreso:
                        callback_progreso({
                            "evento": "esperando",
                            "segundos_restantes": seg_restante,
                            "pausa_total": pausa_humana,
                            "indice": idx + 1,
                            "total": total_items,
                            "siguiente_cliente": siguiente_nombre,
                            "enviados": resultados["enviados"],
                            "fallidos": resultados["fallidos"]
                        })
                    time.sleep(1)

                fraccion = pausa_humana - segundos_enteros
                if fraccion > 0 and not self._cancelar_cola:
                    time.sleep(fraccion)

        self.cola_en_ejecucion = False
        if callback_progreso and not self._cancelar_cola:
            callback_progreso({
                "evento": "finalizado",
                "total": total_items,
                "enviados": resultados["enviados"],
                "fallidos": resultados["fallidos"],
                "resultados": resultados
            })

        return resultados

    # ==========================================
    # GESTIÓN DEL PROGRAMADOR DE TAREAS (schedule)
    # ==========================================
    def programar_revision_periodica(self, minutos: int = 60, smtp: Optional[SMTPManager] = None):
        """
        Programa la verificación y ejecución de reglas cada X minutos usando 'schedule'.
        """
        schedule.clear()
        schedule.every(minutos).minutes.do(self.evaluar_y_ejecutar, smtp=smtp)
        logging.info(f"Programador configurado: ejecución cada {minutos} minutos.")

    def iniciar_demonio_schedule(self, intervalo_chequeo_segundos: int = 5):
        """
        Inicia un hilo en segundo plano (daemon) para correr las tareas pendientes de schedule.
        """
        if self._scheduler_running:
            logging.info("El hilo de schedule ya se encuentra en ejecución.")
            return

        self._scheduler_running = True

        def runner():
            logging.info("Hilo en segundo plano de 'schedule' iniciado.")
            while self._scheduler_running:
                schedule.run_pending()
                time.sleep(intervalo_chequeo_segundos)
            logging.info("Hilo en segundo plano de 'schedule' finalizado.")

        self._scheduler_thread = threading.Thread(target=runner, daemon=True)
        self._scheduler_thread.start()

    def detener_demonio_schedule(self):
        """Detiene la ejecución del hilo de schedule."""
        self._scheduler_running = False

    def cerrar(self):
        """Detiene el scheduler y cierra el navegador de WhatsApp si estuviera en uso."""
        self.detener_demonio_schedule()
        if self.whatsapp_gestor:
            try:
                self.whatsapp_gestor.cerrar()
            except Exception as e:
                logging.warning(f"Error al cerrar gestor de WhatsApp: {e}")
            finally:
                self.whatsapp_gestor = None


# ==========================================
# Ejemplo de uso
# ==========================================
if __name__ == "__main__":
    db_prueba = MinimarketDB("test_minimarket.db")
    automador = Automator(db_prueba)

    print("=== Automator listo con soporte para schedule, SMTP y WhatsApp ===")
    print("Reglas configuradas:", len(db_prueba.get_all_reglas()))
    
    # Programar cada 30 minutos como demostración de schedule
    automador.programar_revision_periodica(minutos=30)
