import sqlite3
import logging
from typing import Optional, List, Dict, Any

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
