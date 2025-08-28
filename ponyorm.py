import json
import uuid
from pony.orm import Database, Required, Optional, PrimaryKey, Set
import datetime

db = Database()

class DatabaseORM:
    def __init__(self, user, password, host, database):
        self.db = db
        self.db.bind(
            provider="postgres",
            user=user,
            password=password,
            host=host,
            database=database
        )
        self._define_entities()
        self.db.generate_mapping(create_tables=True)

    def _define_entities(self):
        db = self.db

        class Carrera(db.Entity):
            id = PrimaryKey(int, auto=True)
            nombre = Required(str)
            codigo = Required(str, unique=True)
            otros = Optional(str)
            planes = Set("PlanDeEstudio")
            
        class Pila(db.Entity):
            id = PrimaryKey(str, default=lambda: str(uuid.uuid4()))  # Generación automática de ID único
            instruccion = Required(str)  # Tipo de instrucción (GET, POST, UPDATE)
            modelo = Required(str)  # Nombre del modelo relacionado
            estado = Required(str, default="pendiente")  # Estado de la tarea (pendiente, procesado, etc.)
            datos = Required(str)  # El modelo serializado en formato JSON
            
        class PlanDeEstudio(db.Entity):
            id = PrimaryKey(int, auto=True)
            nombre = Required(str)
            codigo = Required(str, unique=True)
            fecha = Optional(datetime.date)
            estado = Optional(str)
            carrera = Required(Carrera)
            materias = Set("Materia")

        class Nivel(db.Entity):
            id = PrimaryKey(int, auto=True)
            nivel = Required(int)
            materias = Set("Materia")

        class Materia(db.Entity):
            id = PrimaryKey(int, auto=True)
            sigla = Required(str, unique=True)
            nombre = Required(str)
            creditos = Required(int)
            plan = Required(PlanDeEstudio)
            nivel = Required(Nivel)
            prerequisitos = Set("Prerequisito", reverse="materia")
            es_requisito_de = Set("Prerequisito", reverse="materia_requisito")
            grupos = Set("GrupoMateria")

        class Prerequisito(db.Entity):
            id = PrimaryKey(int, auto=True)
            materia = Required(Materia, reverse="prerequisitos")
            materia_requisito = Required(Materia, reverse="es_requisito_de")

        class Docente(db.Entity):
            id = PrimaryKey(int, auto=True)
            registro = Required(str, unique=True)
            ci = Required(str, unique=True)
            nombre = Required(str)
            telefono = Optional(str)
            otros = Optional(str)
            grupos = Set("GrupoMateria")
            
            
            
        class Gestion(db.Entity):
            id = PrimaryKey(int, auto=True)
            anio = Required(int)
            periodos = Set("Periodo")

        class TipoPeriodo(db.Entity):
            id = PrimaryKey(int, auto=True)
            nombre = Required(str)
            periodos = Set("Periodo")

        class Periodo(db.Entity):
            id = PrimaryKey(int, auto=True)
            numero = Required(str)
            descripcion = Optional(str)
            gestion = Required(Gestion)
            tipoperiodo = Required(TipoPeriodo)
            inscripciones = Set("Inscripcion")
            grupos = Set("GrupoMateria")       #  Relación inversa: un periodo tiene varios grupos


        class GrupoMateria(db.Entity):
            id = PrimaryKey(int, auto=True)
            grupo = Required(str)
            nombre = Optional(str)
            estado = Optional(str)
            materia = Required(Materia)
            docente = Required(Docente)
            periodo = Required(Periodo)        # relación al periodo
            horarios = Set("Horario")
            inscripciones = Set("InscripcionMateria")

       
        class Modulo(db.Entity):
            id = PrimaryKey(int, auto=True)
            numero = Required(str)          # ej: "112"
            nombre = Optional(str)          # ej: "Edificio Principal"
            aulas = Set("Aula")             # contiene varias aulas

        class Aula(db.Entity):
            id = PrimaryKey(int, auto=True)
            numero = Required(str)          
            nombre = Optional(str)          
            modulo = Required(Modulo)      
            horarios = Set("Horario")       

        class Horario(db.Entity):
            id = PrimaryKey(int, auto=True)
            dia = Required(str)
            hora_inicio = Required(datetime.time)
            hora_fin = Required(datetime.time)
            grupo = Required(GrupoMateria)
            aula = Optional(Aula)

        class Estudiante(db.Entity):
            id = PrimaryKey(int, auto=True)
            registro = Required(str, unique=True)
            ci = Required(str, unique=True)
            nombre = Required(str)
            telefono = Optional(str)
            correo = Optional(str)
            otros = Optional(str)
            inscripciones = Set("Inscripcion")

        class Inscripcion(db.Entity):
            id = PrimaryKey(int, auto=True)
            fecha = Required(datetime.date)
            estudiante = Required(Estudiante)
            periodo = Required(Periodo)
            materias = Set("InscripcionMateria")

        class InscripcionMateria(db.Entity):
            id = PrimaryKey(int, auto=True)
            inscripcion = Required(Inscripcion)
            grupo = Required(GrupoMateria)
            notas = Set("Nota")

        class Nota(db.Entity):
            id = PrimaryKey(int, auto=True)
            nota = Required(float)
            inscripcion_materia = Required(InscripcionMateria)
