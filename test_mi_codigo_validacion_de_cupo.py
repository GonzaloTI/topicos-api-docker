import pytest
from unittest.mock import MagicMock  # 'mocker' de pytest-mock usa esto por debajo
from app_except import AppError
#comando para ver con detalles   python -m pytest -v  python -m pytest -v -s


# Asegúrate de que el archivo del canvas (inscripcion_refactorizada.py) 
# esté en el mismo directorio o sea importable.
# Asumimos que la clase se llama 'MiClaseDeLogica' como en el ejemplo anterior.
from cola2 import Cola2
from task_manager import WorkerManager
from task_manager import TaskWorker

# --- Preparación (Fixture) ---
# Esto crea una instancia "fresca" de tu clase para cada prueba
@pytest.fixture
def servicio_inscripcion(mocker):
    """
    Crea una instancia de tu clase, "mockeando" (simulando) 
    sus dependencias de BD y logger.
    """
    # 1. Simular el objeto 'dborm' completo
    mock_dborm = mocker.MagicMock() 
    
    # 2. Instanciar tu clase con el objeto simulado
    # (Ajusta esto a cómo se construya tu clase real)
    
    REDIS_HOST = "localhost"     # ej: "54.210.xxx.xxx"
    REDIS_PORT = 6379
    REDIS_PASSWORD = "contraseniasegura2025"
        
    cola = Cola2(
    redis_host=REDIS_HOST,
    redis_port=REDIS_PORT,
    redis_password=REDIS_PASSWORD,  # tu password
    redis_db=2,
    nombre="cola"
    )
    servicio =   TaskWorker(
                    cola2=cola,
                    dborm=mock_dborm,
                    name="worker_test",
                    bzpop_timeout=1
                )
    
    # 3. Simular el logger para que no intente escribir logs
    servicio.logger = mocker.MagicMock() 
    
    # Devolvemos la instancia del servicio y el mock de la BD
    # para poder usarlos en las pruebas.
    return servicio, mock_dborm

# --- Pruebas Unitarias ---

def test_validar_cupos_exitoso(servicio_inscripcion, mocker):
    """
    Prueba el "camino feliz": el grupo existe y tiene cupos.
    """
    servicio, mock_dborm = servicio_inscripcion
    
    # 1. PREPARAR (Arrange)
    # Simular un objeto "grupo" falso que devolerá la BD
    grupo_falso = mocker.MagicMock()
    
    grupo_falso.id = 101
    grupo_falso.grupo = "GR-01A"  # Campo 'grupo' (Required)
    grupo_falso.nombre = "Cálculo I - Grupo A"
    grupo_falso.estado = "Activo"  # Campo 'estado' (Optional)
    grupo_falso.cupo = 5  # <-- TIENE CUPO
    
    # --- Simular Grupo 2 (ID 10) ---
    grupo_falso_2 = mocker.MagicMock()
    grupo_falso_2.id = 10
    grupo_falso_2.grupo = "GR-02B"
    grupo_falso_2.nombre = "Álgebra - Grupo B"
    grupo_falso_2.estado = "Activo"
    grupo_falso_2.cupo = 20 # <-- TIENE CUPO
    
    
    # --- MODIFICACIÓN PARA MÚLTIPLES GRUPOS ---
    mapa_de_grupos = {
        101: grupo_falso,
        10: grupo_falso_2
    }
    
    # Usamos .side_effect para que 'get' llame a una función
    # que busque en nuestro mapa.
    def mock_get_grupo(id):
        return mapa_de_grupos.get(id) # Devuelve el grupo o None si no está

    # Le decimos al mock que use nuestra función 'mock_get_grupo'
    # cada vez que se llame a 'get'
    mock_dborm.db.GrupoMateria.get.side_effect = mock_get_grupo
    
    # 2. ACTUAR (Act)
    # Llamamos a la función que queremos probar
    grupos_ids = [101,10]
    grupos_validados = servicio._validar_grupos_y_cupos(grupos_ids)
    
    print(f"\n[RESULTADO]: 'grupos_validados' devolvió: {grupos_validados}")
    # 3. VERIFICAR (Assert)
    assert len(grupos_validados) == 2
    assert grupos_validados[0].id == 101
    assert grupos_validados[1].id == 10
    
    # Verificar que el mock fue llamado correctamente
    assert mock_dborm.db.GrupoMateria.get.call_count == 2
    mock_dborm.db.GrupoMateria.get.assert_any_call(id=101)
    mock_dborm.db.GrupoMateria.get.assert_any_call(id=10)


def test_validar_cupos_SIN_CUPO(servicio_inscripcion, mocker):
    """
    Prueba el caso de error: el grupo existe pero no tiene cupos (cupo = 0).
    """
    servicio, mock_dborm = servicio_inscripcion
    
    # 1. PREPARAR
    grupo_falso_lleno = mocker.MagicMock()
    grupo_falso_lleno.id = 102
    grupo_falso_lleno.nombre = "Álgebra - Grupo B"
    grupo_falso_lleno.cupo = 0  # <-- NO TIENE CUPO
    
    mock_dborm.db.GrupoMateria.get.return_value = grupo_falso_lleno
    
    # 2. ACTUAR y 3. VERIFICAR (en una sola línea)
    # Verificamos que la función lanza un 'ValueError'
    # y que el mensaje de error contiene "No hay cupos disponibles"
    # with pytest.raises(ValueError, match="No hay cupos disponibles"):
    #     servicio._validar_grupos_y_cupos(grupos_ids=[102])
        
    with pytest.raises(AppError, match="No hay cupos disponibles"):
        servicio._validar_grupos_y_cupos(grupos_ids=[102])
        
    # Verificar que el mock fue llamado
    mock_dborm.db.GrupoMateria.get.assert_called_with(id=102)


def test_validar_cupos_GRUPO_NO_ENCONTRADO(servicio_inscripcion, mocker):
    """
    Prueba el caso de error: el ID del grupo no existe (la BD devuelve None).
    """
    servicio, mock_dborm = servicio_inscripcion
    
    # 1. PREPARAR
    # Configurar el Mock: "Cuando te llamen, devuelve None"
    mock_dborm.db.GrupoMateria.get.return_value = None
    
    # 2. ACTUAR y 3. VERIFICAR
    # Verificamos que lanza el error con el mensaje correcto
    # with pytest.raises(ValueError, match="grupo con ID 999 no fue encontrado"):
    #     servicio._validar_grupos_y_cupos(grupos_ids=[999])
    with pytest.raises(AppError, match="grupo con ID 999 no fue encontrado"):
        servicio._validar_grupos_y_cupos(grupos_ids=[999])
        
    mock_dborm.db.GrupoMateria.get.assert_called_with(id=999)


def test_validar_cupos_LISTA_VACIA(servicio_inscripcion):
    """
    Prueba el caso de error: la lista de grupos_ids está vacía.
    Esta prueba no necesita mocks de BD, porque la función falla antes.
    """
    servicio, _ = servicio_inscripcion
    
    # 2. ACTUAR y 3. VERIFICAR
    # with pytest.raises(ValueError, match="lista 'grupos_ids' es requerida"):
    #     servicio._validar_grupos_y_cupos(grupos_ids=[])
        
    with pytest.raises(AppError, match="lista 'grupos_ids' es requerida"):
        servicio._validar_grupos_y_cupos(grupos_ids=[])

