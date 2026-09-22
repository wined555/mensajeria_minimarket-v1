import sqlite3
import logging
from typing import Optional, List, Dict, Any

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# CATÁLOGO DE REGLAS Y MODELOS PREDETERMINADOS PARA NEGOCIO DE MINIMARKET
# ==============================================================================
REGLAS_PREDETERMINADAS_MINIMARKET = [
    # --- MODELOS / REGLAS PARA WHATSAPP ---
    {
        "nombre_regla": "🛒 Ofertas del Día en Abarrotes y Despensa",
        "tipo": "WhatsApp",
        "condicion": "Activo",
        "mensaje": (
            "¡Hola {nombre}! 🛒 En *Minimarket* cuidamos tu economía familiar hoy {fecha}:\n\n"
            "🔥 *Arroz, azúcar y aceites* con 15% de descuento\n"
            "🥛 *Lácteos y embutidos frescos* a precios especiales de rebaja\n"
            "🥫 *3x2* en conservas, fideos y salsas seleccionadas\n\n"
            "📍 ¡Visítanos hoy o haz tu pedido por aquí y te lo llevamos volando a casa! 🛵💨"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🥑 Frutas y Verduras Fresquitas del Día",
        "tipo": "WhatsApp",
        "condicion": "Activo",
        "mensaje": (
            "¡Hola {nombre}! 🥑🍎 ¡Llegó mercadería fresquita a *Minimarket* hoy {fecha}!\n\n"
            "🥗 *Paltas cremosas, tomates, lechugas y verduras del día*\n"
            "🍌 *Plátanos dulces, manzanas, naranjas y frutas de temporada*\n"
            "🥚 *Huevos frescos de granja* por docena y maple al mejor precio\n\n"
            "✨ ¡Calidad y frescura garantizada para tu familia! Pasa por tu compra o pídelo a domicilio. 🛵💨"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🥖 Pan Caliente, Empanadas y Desayunos",
        "tipo": "WhatsApp",
        "condicion": "Activo",
        "mensaje": (
            "¡Buenos días {nombre}! 🥖☀️\n\n"
            "En *Minimarket* ya salió la primera tanda de *pan caliente y crujiente* recién horneado:\n\n"
            "☕ Café selecto, leche fresca, huevos y mermeladas\n"
            "🥐 Empanaditas calientes y bocadillos para tu mañana\n"
            "🧀 Jamones y quesos frescos rebanados al instante\n\n"
            "¡Empieza tu día con la mejor energía! Te esperamos antes de que se termine. 🥐✨"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🥩 Carnicería y Embutidos de Calidad",
        "tipo": "WhatsApp",
        "condicion": "Activo",
        "mensaje": (
            "¡Hola {nombre}! 🥩🍗 Hoy en *Minimarket* tenemos los mejores cortes y embutidos para tu almuerzo:\n\n"
            "🍗 *Pollo fresco y carnes seleccionadas*\n"
            "🥓 *Embutidos, chorizos parrilleros y salchichas*\n"
            "🧈 *Mantequilla y quesos artesanales*\n\n"
            "¡Ahorra sin sacrificar calidad en tu mesa! Haz tu encargo por aquí. 🛵🛒"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🥤 Combo Fin de Semana: Cervezas, Snacks y Bebidas",
        "tipo": "WhatsApp",
        "condicion": "Activo",
        "mensaje": (
            "¡Hola {nombre}! 🍿🍻 ¡Llegó el fin de semana a *Minimarket*!\n\n"
            "❄️ *Cervezas, gaseosas y jugos al polo* (bien heladas)\n"
            "🍟 *Snacks, papitas, chocolates, galletas y piqueos en oferta*\n"
            "🧊 *Bolsas de hielo y carbón* listos para tu reunión o parrilla\n\n"
            "🎉 ¡No salgas de casa! Pide tu combo por WhatsApp y te lo llevamos en minutos. 🛵💨"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🧼 Pack Ahorro Hogar: Limpieza y Aseo",
        "tipo": "WhatsApp",
        "condicion": "Activo",
        "mensaje": (
            "¡Hola {nombre}! 🧼✨ En *Minimarket* armamos packs de ahorro para que tu hogar quede impecable:\n\n"
            "🧺 *Detergentes y suavizantes* en tamaño económico\n"
            "🧽 *Lavavajillas, desinfectantes y lavandina multiusos*\n"
            "🧻 *Papel higiénico y toallas de cocina* en paquetes familiares\n\n"
            "¡Ven por tu pack de ahorro o solicítalo a domicilio hoy mismo! 🏪👍"
        ),
        "activa": True
    },
    {
        "nombre_regla": "⭐ Cliente VIP: Descuento Exclusivo",
        "tipo": "WhatsApp",
        "condicion": "VIP",
        "mensaje": (
            "¡Estimado(a) {nombre}! ⭐ En *Minimarket* premiamos tu preferencia constante:\n\n"
            "👑 Como cliente especial categoría {categoria}, hoy tienes un *descuento exclusivo del 10%* en tu próxima compra o delivery.\n"
            "¡Gracias por ser parte de nuestra gran familia! Estamos a tu orden. 🏪🤝"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🛵 Delivery Express a Domicilio (Pedido Fácil)",
        "tipo": "WhatsApp",
        "condicion": "Activo",
        "mensaje": (
            "¡Hola {nombre}! 🛵 ¿Te falta algo en la cocina o en tu despensa?\n\n"
            "¡En *Minimarket* te lo llevamos hasta la puerta de tu casa en minutos!\n"
            "📲 Solo envíanos tu lista de compras por este chat.\n"
            "💳 Aceptamos efectivo, transferencia bancaria, pago QR o tarjeta.\n\n"
            "¡Rápido, cómodo y seguro! Escríbenos cuando lo necesites. 🏪📦"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🎂 Saludo de Cumpleaños / Descuento Especial",
        "tipo": "WhatsApp",
        "condicion": "Activo",
        "mensaje": (
            "¡Feliz Cumpleaños {nombre}! 🎂🎉🎈\n\n"
            "En *Minimarket* estamos felices de celebrar contigo en este día especial.\n"
            "🎁 Hoy tienes un *15% de descuento en toda tu compra* presentando este mensaje.\n\n"
            "¡Que pases un día maravilloso junto a tu familia! 🥳✨"
        ),
        "activa": True
    },
    {
        "nombre_regla": "💰 Recordatorio Amable de Saldo / Fiado",
        "tipo": "WhatsApp",
        "condicion": "Activo",
        "mensaje": (
            "Estimado(a) {nombre}, le saludamos cordialmente de *Minimarket*. 🏪\n\n"
            "Le recordamos de manera amable que mantiene un saldo pendiente por compras recientes en nuestra tienda.\n"
            "Agradeceremos pueda pasar a cancelar o realizar su pago vía QR / transferencia a su comodidad.\n\n"
            "¡Agradecemos mucho su confianza y comprensión! Cualquier duda estamos a su servicio. 👍"
        ),
        "activa": True
    },
    # --- MODELOS / REGLAS PARA CORREO SMTP ---
    {
        "nombre_regla": "🛒 Super Ofertas Semanales de Despensa y Canasta Básica",
        "tipo": "Correo SMTP",
        "condicion": "Activo",
        "mensaje": (
            "Asunto: 🛒 ¡Ahorra en grande esta semana en {minimarket}! Ofertas exclusivas para ti\n\n"
            "Estimado(a) {nombre},\n\n"
            "Esperamos que se encuentre muy bien. En {minimarket} queremos cuidar su economía familiar, "
            "por lo que esta semana traemos descuentos especiales en productos esenciales de la canasta básica:\n\n"
            "✅ Arroz, azúcar y aceite de las mejores marcas con hasta 15% de descuento.\n"
            "✅ Leche, yogures y quesos frescos seleccionados para su familia.\n"
            "✅ Promoción 3x2 en fideos, conservas y salsas de tomate.\n"
            "✅ Descuentos imperdibles en artículos de limpieza y aseo personal.\n\n"
            "📅 Promoción válida del {fecha} hasta agotar stock.\n"
            "📍 Visítenos hoy mismo o realice su pedido a domicilio y se lo llevamos directamente a su puerta.\n\n"
            "¡Agradecemos su preferencia y fidelidad!\n\n"
            "Atentamente,\n"
            "El equipo de {minimarket} 🏪"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🥑 Llegada de Frutas, Verduras y Lácteos Frescos",
        "tipo": "Correo SMTP",
        "condicion": "Activo",
        "mensaje": (
            "Asunto: 🥑 ¡Mercadería Fresca recién llegada a {minimarket}! Frutas y verduras del día\n\n"
            "¡Hola {nombre}!\n\n"
            "Le informamos que hoy {fecha} acabamos de recibir nuestro camión con las frutas y verduras más frescas del mercado:\n\n"
            "🥦 Paltas cremosas, tomates maduros, lechugas frescas y verduras del día.\n"
            "🍎 Manzanas crujientes, plátanos dulces, naranjas para jugo y frutas de temporada.\n"
            "🥚 Huevos frescos de granja por docena y maple al mejor precio.\n"
            "🥛 Lácteos y derivados frescos garantizados.\n\n"
            "Disfrute de la máxima frescura y calidad que su mesa familiar merece.\n\n"
            "¡Pase por su compra o escríbanos para apartar sus productos favoritos antes de que se agoten!\n\n"
            "Saludos cordiales,\n"
            "{minimarket} 🏪"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🥩 Carnicería, Embutidos y Lácteos a Precios Especiales",
        "tipo": "Correo SMTP",
        "condicion": "Activo",
        "mensaje": (
            "Asunto: 🥩 Calidad y Frescura: Carnes, embutidos y cortes selectos en {minimarket}\n\n"
            "Estimado(a) {nombre},\n\n"
            "Para sus almuerzos y preparaciones familiares, en {minimarket} le ofrecemos los cortes y embutidos más frescos:\n\n"
            "🍗 Pollo fresco, carnes seleccionadas y cortes listos para la semana.\n"
            "🥓 Jamones, salchichas, chorizos y embutidos de primera calidad.\n"
            "🧈 Mantequilla, queso criollo y lácteos artesanales.\n\n"
            "Precios competitivos y la mejor higiene y conservación garantizada.\n\n"
            "¡Le esperamos con la cordialidad de siempre!\n\n"
            "Atentamente,\n"
            "{minimarket} 🏪"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🥐 Desayunos y Pan Caliente Recién Horneado",
        "tipo": "Correo SMTP",
        "condicion": "Activo",
        "mensaje": (
            "Asunto: 🥐🥖 ¡Empieza tu día con pan calientito y desayunos en {minimarket}!\n\n"
            "¡Buenos días {nombre}!\n\n"
            "En {minimarket} ya tenemos el pan caliente, crujiente y recién salido del horno listo para su desayuno:\n\n"
            "☕ Acompañe su mañana con café selecto, leche fresca, té, mermeladas y quesos.\n"
            "🥪 Empanadas y bocadillos recién preparados.\n"
            "🧀 Fiambres y quesos cortados al gusto.\n\n"
            "Abiertos desde muy temprano para que empiece su jornada con la mejor energía.\n\n"
            "¡Que tenga un excelente día!\n\n"
            "{minimarket} 🏪"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🥤 Combo Fin de Semana: Snacks, Bebidas y Cervezas Heladas",
        "tipo": "Correo SMTP",
        "condicion": "Activo",
        "mensaje": (
            "Asunto: 🎉 ¡Llegó el Fin de Semana! Snacks, piqueos y bebidas heladas en {minimarket}\n\n"
            "¡Hola {nombre}!\n\n"
            "¿Planes para descansar o compartir con familia y amigos este fin de semana? En {minimarket} tenemos todo listo:\n\n"
            "❄️ Cervezas, gaseosas, aguas y jugos al polo (bien heladas).\n"
            "🍿 Papitas, piqueos, chocolates, galletas y snacks surtidos.\n"
            "🧊 Bolsas de hielo, vasos descartables y carbón para su parrilla.\n\n"
            "No se preocupe por salir: solicite su pedido a domicilio y se lo entregamos en minutos.\n\n"
            "¡A disfrutar el fin de semana!\n\n"
            "{minimarket} 🏪"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🧼 Pack Ahorro Hogar: Limpieza y Aseo Familiar",
        "tipo": "Correo SMTP",
        "condicion": "Activo",
        "mensaje": (
            "Asunto: 🧼 ¡Tu Hogar Impecable! Ofertas en productos de limpieza en {minimarket}\n\n"
            "Estimado(a) {nombre},\n\n"
            "Mantener su hogar limpio y desinfectado ahora cuesta menos en {minimarket}:\n\n"
            "🧺 Detergentes en polvo y líquidos en formatos económicos familiares.\n"
            "✨ Lavavajillas, desinfectantes multiusos y lavandina.\n"
            "🧻 Papel higiénico, servilletas y toallas de cocina en paquetes familiares.\n\n"
            "Calidad y rendimiento comprobado para cuidar el presupuesto de su hogar.\n\n"
            "¡Visítenos hoy o solicite su despacho a domicilio!\n\n"
            "Atentamente,\n"
            "Administración de {minimarket} 🏪"
        ),
        "activa": True
    },
    {
        "nombre_regla": "⭐ Programa Cliente VIP: Beneficio Exclusivo del Mes",
        "tipo": "Correo SMTP",
        "condicion": "VIP",
        "mensaje": (
            "Asunto: ⭐ Eres un Cliente VIP en {minimarket}: Accede a beneficios exclusivos\n\n"
            "Estimado(a) {nombre},\n\n"
            "Queremos agradecerle especialmente por su lealtad y confianza constante en {minimarket}.\n\n"
            "Como cliente preferencial en categoría {categoria}, este mes cuenta con beneficios únicos en nuestra tienda:\n"
            "🌟 Precios preferenciales en compras por mayor y canasta familiar.\n"
            "🌟 Descuento del 10% en sus compras de fin de semana.\n"
            "🌟 Atención prioritaria en pedidos a domicilio y reserva de stock.\n\n"
            "¡Será un gusto atenderle siempre con el trato y dedicación que usted merece!\n\n"
            "Cordialmente,\n"
            "Gerencia de {minimarket} 🏪"
        ),
        "activa": True
    },
    {
        "nombre_regla": "🎂 Descuento de Cumpleaños para Clientes Frecuentes",
        "tipo": "Correo SMTP",
        "condicion": "Activo",
        "mensaje": (
            "Asunto: 🎂🎁 ¡Feliz Cumpleaños {nombre}! Tenemos un regalo especial para ti en {minimarket}\n\n"
            "¡Feliz Cumpleaños {nombre}! 🎉🎂🎈\n\n"
            "De parte de toda la familia de {minimarket}, queremos desearle un día lleno de bendiciones, salud y alegría junto a sus seres queridos.\n\n"
            "🎁 Para celebrarlo con usted, le obsequiamos un 15% de descuento en toda su compra durante la semana de su cumpleaños presentando este correo.\n\n"
            "¡Gracias por ser un cliente tan valioso para nosotros!\n\n"
            "Un abrazo cordial,\n"
            "{minimarket} 🏪"
        ),
        "activa": True
    },
    {
        "nombre_regla": "💰 Recordatorio Cordial de Saldo Pendiente",
        "tipo": "Correo SMTP",
        "condicion": "Activo",
        "mensaje": (
            "Asunto: 🏪 Estado de Cuenta / Saldo Pendiente en {minimarket}\n\n"
            "Estimado(a) {nombre},\n\n"
            "Le enviamos un saludo cordial de parte de la administración de {minimarket}.\n\n"
            "Nos comunicamos respetuosamente para informarle que registra un saldo pendiente de pago correspondiente a sus compras recientes en nuestra tienda.\n\n"
            "Agradeceremos pueda pasar por el local para regularizar su cuenta a la brevedad posible, o realizar su abono a través de transferencia bancaria o código QR.\n\n"
            "Si ya realizó su pago recientemente, por favor desestime este mensaje. Para cualquier consulta o detalle del saldo, estamos a su total disposición.\n\n"
            "Muchas gracias por su atención y comprensión.\n\n"
            "Atentamente,\n"
            "Administración de {minimarket} 🏪"
        ),
        "activa": True
    },
    {
        "nombre_regla": "⏰ Horarios de Atención, Medios de Pago y Delivery",
        "tipo": "Correo SMTP",
        "condicion": "Activo",
        "mensaje": (
            "Asunto: 🏪 Novedades, Delivery y Horarios de Atención en {minimarket}\n\n"
            "Estimado(a) cliente {nombre},\n\n"
            "En {minimarket} renovamos nuestro compromiso de brindarle el mejor servicio, variedad y comodidad:\n\n"
            "⏰ Horario continuo de atención: Lunes a Domingo de 7:00 AM a 10:00 PM.\n"
            "🛵 Servicio de Delivery express en minutos hasta su puerta.\n"
            "💳 Medios de pago disponibles: Efectivo, Tarjetas de Débito/Crédito, Transferencia bancaria y pagos con QR.\n\n"
            "¡Siempre cerca de su hogar para atenderle con una sonrisa!\n\n"
            "Atentamente,\n"
            "{minimarket} 🏪"
        ),
        "activa": True
    }
]

class MinimarketDB:
    """Clase para gestionar la base de datos SQLite del minimarket."""
    
    def __init__(self, db_name: str = "minimarket.db"):
        self.db_name = db_name
        self.create_tables()

    def _get_connection(self):
        """Establece y retorna una conexión a la base de datos."""
        try:
            conn = sqlite3.connect(self.db_name)
            conn.row_factory = sqlite3.Row  # Permite acceder a las columnas por nombre
            # Habilitar soporte para foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except sqlite3.Error as e:
            logging.error(f"Error al conectar con la base de datos: {e}")
            raise

    def create_tables(self):
        """Crea las tablas necesarias si no existen."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Tabla Clientes
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS clientes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nombre TEXT NOT NULL,
                        correo TEXT,
                        telefono TEXT,
                        estado TEXT,
                        categoria TEXT DEFAULT '🥉 Bronce'
                    )
                ''')

                # Migración automática si la columna categoria no existía previamente
                try:
                    cursor.execute("ALTER TABLE clientes ADD COLUMN categoria TEXT DEFAULT '🥉 Bronce'")
                except sqlite3.OperationalError:
                    pass

                # Normalización de datos heredados (ej. clientes con estado 'VIP' o 'Nuevo')
                try:
                    cursor.execute("UPDATE clientes SET categoria = '✨ Diamante / VIP' WHERE UPPER(estado) = 'VIP' AND (categoria IS NULL OR categoria = '🥉 Bronce')")
                    cursor.execute("UPDATE clientes SET estado = 'Activo' WHERE estado IS NOT NULL AND estado NOT IN ('Activo', 'Inactivo')")
                    cursor.execute("UPDATE clientes SET categoria = '🥉 Bronce' WHERE categoria IS NULL OR categoria = ''")
                except sqlite3.OperationalError:
                    pass
                
                # Tabla Reglas
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS reglas (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nombre_regla TEXT NOT NULL,
                        tipo TEXT,
                        condicion TEXT,
                        mensaje TEXT,
                        activa BOOLEAN DEFAULT 1
                    )
                ''')
                
                # Tabla Historial
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS historial (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cliente_id INTEGER,
                        fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                        estado TEXT,
                        FOREIGN KEY (cliente_id) REFERENCES clientes (id) ON DELETE CASCADE
                    )
                ''')

                # Tabla Configuración (Ajustes y Credenciales)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS configuracion (
                        clave TEXT PRIMARY KEY,
                        valor TEXT
                    )
                ''')
                conn.commit()
                logging.info("Tablas creadas o verificadas exitosamente.")
        except sqlite3.Error as e:
            logging.error(f"Error al crear las tablas: {e}")
            raise

        try:
            self._verificar_e_inicializar_reglas()
        except Exception as e:
            logging.warning(f"Aviso al inicializar reglas predeterminadas: {e}")

    # ==========================
    # CRUD para Clientes
    # ==========================
    def create_cliente(self, nombre: str, correo: str, telefono: str, estado: str = "Activo", categoria: str = "🥉 Bronce") -> Optional[int]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO clientes (nombre, correo, telefono, estado, categoria) VALUES (?, ?, ?, ?, ?)",
                    (nombre, correo, telefono, estado, categoria)
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error al crear cliente: {e}")
            return None

    def get_cliente(self, cliente_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logging.error(f"Error al leer cliente: {e}")
            return None

    def get_all_clientes(self) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM clientes")
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error al obtener clientes: {e}")
            return []

    def update_cliente(self, cliente_id: int, nombre: str = None, correo: str = None, telefono: str = None, estado: str = None, categoria: str = None) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Construir consulta dinámica
                campos = []
                valores = []
                if nombre is not None: campos.append("nombre = ?"); valores.append(nombre)
                if correo is not None: campos.append("correo = ?"); valores.append(correo)
                if telefono is not None: campos.append("telefono = ?"); valores.append(telefono)
                if estado is not None: campos.append("estado = ?"); valores.append(estado)
                if categoria is not None: campos.append("categoria = ?"); valores.append(categoria)
                
                if not campos:
                    return False
                
                valores.append(cliente_id)
                query = f"UPDATE clientes SET {', '.join(campos)} WHERE id = ?"
                
                cursor.execute(query, tuple(valores))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logging.error(f"Error al actualizar cliente: {e}")
            return False

    def delete_cliente(self, cliente_id: int) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logging.error(f"Error al eliminar cliente: {e}")
            return False

    # ==========================
    # CRUD para Reglas
    # ==========================
    def create_regla(self, nombre_regla: str, tipo: str, condicion: str, mensaje: str, activa: bool = True) -> Optional[int]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO reglas (nombre_regla, tipo, condicion, mensaje, activa) VALUES (?, ?, ?, ?, ?)",
                    (nombre_regla, tipo, condicion, mensaje, activa)
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error al crear regla: {e}")
            return None

    def get_regla(self, regla_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM reglas WHERE id = ?", (regla_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logging.error(f"Error al leer regla: {e}")
            return None

    def get_all_reglas(self) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM reglas")
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error al obtener reglas: {e}")
            return []

    def update_regla(self, regla_id: int, nombre_regla: str = None, tipo: str = None, condicion: str = None, mensaje: str = None, activa: bool = None) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                campos = []
                valores = []
                if nombre_regla is not None: campos.append("nombre_regla = ?"); valores.append(nombre_regla)
                if tipo is not None: campos.append("tipo = ?"); valores.append(tipo)
                if condicion is not None: campos.append("condicion = ?"); valores.append(condicion)
                if mensaje is not None: campos.append("mensaje = ?"); valores.append(mensaje)
                if activa is not None: campos.append("activa = ?"); valores.append(activa)
                
                if not campos:
                    return False
                
                valores.append(regla_id)
                query = f"UPDATE reglas SET {', '.join(campos)} WHERE id = ?"
                
                cursor.execute(query, tuple(valores))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logging.error(f"Error al actualizar regla: {e}")
            return False

    def delete_regla(self, regla_id: int) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM reglas WHERE id = ?", (regla_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logging.error(f"Error al eliminar regla: {e}")
            return False

    def _verificar_e_inicializar_reglas(self):
        """Inicializa automáticamente las reglas de minimarket si la base de datos tiene 1 o menos reglas."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as total FROM reglas")
                row = cursor.fetchone()
                total = row["total"] if row else 0
                if total <= 1:
                    self.inicializar_reglas_predeterminadas_minimarket(forzar=False)
        except Exception as e:
            logging.warning(f"Error en verificación inicial de reglas: {e}")

    def inicializar_reglas_predeterminadas_minimarket(self, forzar: bool = False) -> int:
        """
        Inserta las reglas oficiales predeterminadas para Minimarket (WhatsApp y Correo SMTP).
        Si forzar=False, solo inserta las que no existan previamente por nombre.
        Retorna la cantidad de reglas nuevas insertadas.
        """
        insertadas = 0
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT nombre_regla FROM reglas")
                existentes = {row["nombre_regla"].strip().lower() for row in cursor.fetchall()}

                for r in REGLAS_PREDETERMINADAS_MINIMARKET:
                    nom = r["nombre_regla"].strip()
                    if forzar or (nom.lower() not in existentes):
                        cursor.execute(
                            "INSERT INTO reglas (nombre_regla, tipo, condicion, mensaje, activa) VALUES (?, ?, ?, ?, ?)",
                            (nom, r["tipo"], r["condicion"], r["mensaje"], 1 if r.get("activa", True) else 0)
                        )
                        existentes.add(nom.lower())
                        insertadas += 1
                conn.commit()
                if insertadas > 0:
                    logging.info(f"Se inicializaron {insertadas} reglas predeterminadas de Minimarket.")
        except sqlite3.Error as e:
            logging.error(f"Error al inicializar reglas predeterminadas: {e}")
        return insertadas

    # ==========================
    # CRUD para Historial
    # ==========================
    def create_historial(self, cliente_id: int, estado: str, fecha: str = None) -> Optional[int]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if fecha:
                    cursor.execute(
                        "INSERT INTO historial (cliente_id, fecha, estado) VALUES (?, ?, ?)",
                        (cliente_id, fecha, estado)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO historial (cliente_id, estado) VALUES (?, ?)",
                        (cliente_id, estado)
                    )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logging.error(f"Error al crear historial: {e}")
            return None

    def get_historial(self, historial_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM historial WHERE id = ?", (historial_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logging.error(f"Error al leer historial: {e}")
            return None

    def get_historial_por_cliente(self, cliente_id: int) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM historial WHERE cliente_id = ? ORDER BY fecha DESC", (cliente_id,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error al obtener historial del cliente: {e}")
            return []

    def update_historial(self, historial_id: int, cliente_id: int = None, fecha: str = None, estado: str = None) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                campos = []
                valores = []
                if cliente_id is not None: campos.append("cliente_id = ?"); valores.append(cliente_id)
                if fecha is not None: campos.append("fecha = ?"); valores.append(fecha)
                if estado is not None: campos.append("estado = ?"); valores.append(estado)
                
                if not campos:
                    return False
                
                valores.append(historial_id)
                query = f"UPDATE historial SET {', '.join(campos)} WHERE id = ?"
                
                cursor.execute(query, tuple(valores))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logging.error(f"Error al actualizar historial: {e}")
            return False

    def delete_historial(self, historial_id: int) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM historial WHERE id = ?", (historial_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logging.error(f"Error al eliminar historial: {e}")
            return False

    # ==========================
    # Gestión de Configuración y Credenciales
    # ==========================
    def set_config(self, clave: str, valor: str) -> bool:
        """Guarda o actualiza un parámetro de configuración en la base de datos."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
                    "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
                    (clave, valor)
                )
                conn.commit()
                return True
        except sqlite3.Error as e:
            logging.error(f"Error al guardar configuración '{clave}': {e}")
            return False

    def get_config(self, clave: str, default: Optional[str] = None) -> Optional[str]:
        """Obtiene el valor de un parámetro de configuración."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
                row = cursor.fetchone()
                if row and row["valor"] is not None:
                    return str(row["valor"])
                return default
        except sqlite3.Error as e:
            logging.error(f"Error al obtener configuración '{clave}': {e}")
            return default

    def guardar_credenciales_smtp(
        self, 
        email: str, 
        password: str, 
        tls: bool = True, 
        host: str = "smtp.gmail.com", 
        puerto: int = 587
    ) -> bool:
        """Guarda las credenciales y configuración del servidor SMTP."""
        ok1 = self.set_config("smtp_email", email.strip())
        ok2 = self.set_config("smtp_password", password.strip())
        ok3 = self.set_config("smtp_tls", "1" if tls else "0")
        ok4 = self.set_config("smtp_host", host.strip())
        ok5 = self.set_config("smtp_port", str(puerto))
        return ok1 and ok2 and ok3 and ok4 and ok5

    def obtener_credenciales_smtp(self) -> Dict[str, Any]:
        """Recupera las credenciales y configuración SMTP almacenadas en la base de datos."""
        tls_val = self.get_config("smtp_tls", "1")
        puerto_str = self.get_config("smtp_port", "587")
        try:
            puerto_int = int(puerto_str) if puerto_str else 587
        except ValueError:
            puerto_int = 587

        return {
            "email": self.get_config("smtp_email", "") or "",
            "password": self.get_config("smtp_password", "") or "",
            "tls": tls_val != "0",
            "host": self.get_config("smtp_host", "smtp.gmail.com") or "smtp.gmail.com",
            "puerto": puerto_int
        }

    def guardar_tiempos_automatizacion(self, perfil: str, min_seg: int, max_seg: int) -> bool:
        """Guarda la configuración de intervalos de tiempo anti-baneo."""
        ok1 = self.set_config("auto_delay_perfil", perfil.strip())
        ok2 = self.set_config("auto_delay_min", str(min_seg))
        ok3 = self.set_config("auto_delay_max", str(max_seg))
        return ok1 and ok2 and ok3

    def obtener_tiempos_automatizacion(self) -> Dict[str, Any]:
        """Recupera los tiempos anti-baneo configurados (por defecto perfil Humano Seguro: 15-30s)."""
        perfil = self.get_config("auto_delay_perfil", "🛡️ Humano Seguro (15-30s) [Recomendado]")
        try:
            min_seg = int(self.get_config("auto_delay_min", "15"))
        except (ValueError, TypeError):
            min_seg = 15
        try:
            max_seg = int(self.get_config("auto_delay_max", "30"))
        except (ValueError, TypeError):
            max_seg = 30

        return {
            "perfil": perfil or "🛡️ Humano Seguro (15-30s) [Recomendado]",
            "min_seg": min_seg,
            "max_seg": max_seg
        }

# ==========================
# Pruebas Rápidas (Ejecutadas solo al correr este archivo)
# ==========================
if __name__ == "__main__":
    db = MinimarketDB("test_minimarket.db")
    
    # Prueba CRUD Clientes
    cliente_id = db.create_cliente("Juan Perez", "juan@example.com", "555-1234", "Activo")
    print(f"Cliente creado con ID: {cliente_id}")
    print("Cliente leído:", db.get_cliente(cliente_id))
    
    # Prueba CRUD Reglas
    regla_id = db.create_regla("Descuento 10%", "descuento", "compras > 100", "Felicidades, tienes 10% de descuento")
    print(f"Regla creada con ID: {regla_id}")
    print("Regla leída:", db.get_regla(regla_id))
    
    # Prueba CRUD Historial
    historial_id = db.create_historial(cliente_id, "Compra realizada")
    print(f"Historial creado con ID: {historial_id}")
    print("Historial leído:", db.get_historial(historial_id))
    
    # Prueba Actualizaciones
    db.update_cliente(cliente_id, estado="Inactivo")
    print("Cliente actualizado:", db.get_cliente(cliente_id))
