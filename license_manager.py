import subprocess
import os
import logging
from cryptography.fernet import Fernet, InvalidToken

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================
# PARTE 1: Para el Cliente (Obtener Hardware ID)
# ==========================================
def get_hardware_id() -> str:
    """
    Obtiene el UUID de la placa base/sistema en Windows.
    Utiliza PowerShell para asegurar compatibilidad.
    """
    try:
        # Ejecuta PowerShell para obtener el UUID del sistema (SMBIOS UUID)
        cmd = 'powershell -Command "(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID"'
        result = subprocess.check_output(cmd, shell=True, text=True)
        uuid = result.strip()
        if uuid:
            return uuid
        return ""
    except Exception as e:
        logging.error(f"Error al obtener el ID del hardware: {e}")
        return ""


# ==========================================
# PARTE 2: El Validador (y Generador)
# ==========================================
class LicenseManager:
    def __init__(self, key_path: str = "secret.key"):
        """
        Inicializa el gestor con una clave de encriptación (Fernet/AES).
        NOTA: En producción, 'secret.key' no debe entregarse al cliente si es 
        posible, o debe estar ofuscada dentro del código compilado.
        """
        self.key_path = key_path
        self.cipher = None
        self._load_or_create_key()

    def _load_or_create_key(self):
        """Carga la clave de encriptación o crea una nueva si no existe."""
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as key_file:
                key = key_file.read()
                self.cipher = Fernet(key)
        else:
            # Si no existe la llave maestra, la genera (idealmente esto lo haces en tu PC)
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as key_file:
                key_file.write(key)
            self.cipher = Fernet(key)
            logging.warning(f"Nueva clave de encriptación generada en '{self.key_path}'. "
                            f"¡Guárdala bien y NO la compartas con el cliente!")

    def generate_license(self, hardware_id: str, license_path: str = "license.key") -> bool:
        """
        Genera un archivo de licencia encriptado para un hardware específico.
        Este método lo usas tú (el desarrollador) para generar la licencia al cliente.
        """
        if not hardware_id:
            logging.error("No se puede generar licencia sin un ID de hardware.")
            return False

        try:
            # Encriptamos el Hardware ID
            encrypted_id = self.cipher.encrypt(hardware_id.encode())
            
            # Guardamos la licencia encriptada
            with open(license_path, "wb") as lic_file:
                lic_file.write(encrypted_id)
                
            logging.info(f"Licencia generada exitosamente en '{license_path}'.")
            return True
        except Exception as e:
            logging.error(f"Error al generar licencia: {e}")
            return False

    def validate_license(self, license_path: str = "license.key") -> bool:
        """
        Lee el archivo de licencia, lo desencripta y verifica que coincida
        con el hardware actual de la máquina donde se está ejecutando.
        """
        if not os.path.exists(license_path):
            logging.error(f"Archivo de licencia '{license_path}' no encontrado.")
            return False

        try:
            # 1. Leer archivo encriptado
            with open(license_path, "rb") as lic_file:
                encrypted_id = lic_file.read()

            # 2. Desencriptar
            decrypted_id_bytes = self.cipher.decrypt(encrypted_id)
            decrypted_id = decrypted_id_bytes.decode()

            # 3. Obtener el ID de la máquina actual
            current_hardware_id = get_hardware_id()

            # 4. Validar
            if current_hardware_id and current_hardware_id == decrypted_id:
                logging.info("Validación exitosa: ¡Licencia Válida para este equipo!")
                return True
            else:
                logging.error("Licencia Inválida: El UUID del equipo no coincide con la licencia.")
                return False

        except InvalidToken:
            logging.error("Licencia Inválida o corrupta (clave de desencriptación incorrecta).")
            return False
        except Exception as e:
            logging.error(f"Error al validar la licencia: {e}")
            return False

# ==========================================
# Ejemplos de uso / Pruebas
# ==========================================
if __name__ == "__main__":
    print("=== Probando Sistema de Licencias ===")
    
    # 1. Obtener ID de este equipo
    hw_id = get_hardware_id()
    print(f"Hardware ID (UUID) detectado: {hw_id}")
    
    if hw_id:
        manager = LicenseManager()
        
        # 2. Generar licencia para este mismo equipo (Simulando lo que haces como dev)
        print("\n--- Generando Licencia ---")
        manager.generate_license(hw_id)
        
        # 3. Validar licencia (Simulando lo que hace el software en la PC del cliente)
        print("\n--- Validando Licencia ---")
        is_valid = manager.validate_license()
        print(f"¿Es válida? -> {is_valid}")
        
        # 4. Forzar una validación fallida (alterando la licencia)
        print("\n--- Simulando copia en otra PC o licencia alterada ---")
        manager.generate_license("OTRO-UUID-FALSO-1234")
        is_valid_falsa = manager.validate_license()
        print(f"¿Es válida la licencia falsa? -> {is_valid_falsa}")
