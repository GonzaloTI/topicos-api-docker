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
            def to_full_dict(self):
                """incluyendo planes relacionados"""
                data = self.to_dict()
                data["planes"] = [p.to_full_dict() for p in self.planes] if self.planes else []
                return data
            
        class Pila(db.Entity):
            id = PrimaryKey(str, default=lambda: str(uuid.uuid4()))  # Generación de ID unico
            instruccion = Required(str)  # Tipo de instrucción (GET, POST, UPDATE)
            modelo = Required(str)  
            estado = Required(str, default="pendiente") 
            datos = Required(str)  
            
        class PlanDeEstudio(db.Entity):
            id = PrimaryKey(int, auto=True)
            nombre = Required(str)
            codigo = Required(str, unique=True)
            fecha = Optional(datetime.date)
            estado = Optional(str)
            carrera = Required(Carrera)
            materias = Set("Materia")
            
            def to_full_dict(self):
                """Convierte el plan en un dict incluyendo relaciones aun no se usa o_dict(with_collections=True, related_objects=True)"""
                data = self.to_dict()
                if self.fecha:
                    data["fecha"] = self.fecha.isoformat()  # "2025-01-01"
                data["carrera"] = self.carrera.to_dict() if self.carrera else None
                data["materias"] = [m.to_dict() for m in self.materias] if self.materias else []
                return data
            
            

        class Nivel(db.Entity):
            id = PrimaryKey(int, auto=True)
            nivel = Required(int)
            materias = Set("Materia")
            def to_full_dict(self):
                data = self.to_dict()
                data["materias"] = [m.to_full_dict() for m in self.materias] if self.materias else []
                return data

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
            
            def to_full_dict(self):
                """expandiendo relaciones"""
                data = self.to_dict()
                data["plan"] = self.plan.to_dict() if self.plan else None
                data["nivel"] = self.nivel.to_dict() if self.nivel else None
                data["prerequisitos"] = [
                    {"id": pr.id, "materia_requisito": pr.materia_requisito.to_dict()}
                    for pr in self.prerequisitos
                ]
                data["es_requisito_de"] = [
                    {"id": er.id, "materia": er.materia.to_dict()}
                    for er in self.es_requisito_de
                ]
                data["grupos"] = [g.to_dict() for g in self.grupos] if self.grupos else []
                return data

        class Prerequisito(db.Entity):
            id = PrimaryKey(int, auto=True)
            materia = Required(Materia, reverse="prerequisitos")
            materia_requisito = Required(Materia, reverse="es_requisito_de")
            def to_full_dict(self):
                data = self.to_dict()
                data["materia"] = self.materia.to_full_dict() if self.materia else None
                data["materia_requisito"] = self.materia_requisito.to_full_dict() if self.materia_requisito else None
                return data

        class Docente(db.Entity):
            id = PrimaryKey(int, auto=True)
            registro = Required(str, unique=True)
            ci = Required(str, unique=True)
            nombre = Required(str)
            telefono = Optional(str)
            otros = Optional(str)
            grupos = Set("GrupoMateria")
            
            def to_full_dict(self):
                """ incluyendo los grupos donde ensenia"""
                data = self.to_dict()
                data["grupos"] = [g.to_dict() for g in self.grupos] if self.grupos else []
                return data
            
            
            
        class Gestion(db.Entity):
            id = PrimaryKey(int, auto=True)
            anio = Required(int)
            periodos = Set("Periodo")
            def to_full_dict(self):
                data = self.to_dict()
                data["periodos"] = [p.to_dict() for p in self.periodos] if self.periodos else []
                return data

        class TipoPeriodo(db.Entity):
            id = PrimaryKey(int, auto=True)
            nombre = Required(str)
            periodos = Set("Periodo")
            def to_full_dict(self):
                data = self.to_dict()
                data["periodos"] = [p.to_dict() for p in self.periodos] if self.periodos else []
                return data

        class Periodo(db.Entity):
            id = PrimaryKey(int, auto=True)
            numero = Required(str)
            descripcion = Optional(str)
            gestion = Required(Gestion)
            tipoperiodo = Required(TipoPeriodo)
            inscripciones = Set("Inscripcion")
            grupos = Set("GrupoMateria")       #  Relación inversa: un periodo tiene varios grupos
            def to_full_dict(self):
                data = self.to_dict()
                data["gestion"] = self.gestion.to_dict() if self.gestion else None
                data["tipoperiodo"] = self.tipoperiodo.to_dict() if self.tipoperiodo else None
                data["inscripciones"] = [i.to_dict() for i in self.inscripciones] if self.inscripciones else []
                data["grupos"] = [g.to_dict() for g in self.grupos] if self.grupos else []
                return data


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
            def to_full_dict(self):
                data = self.to_dict()
                data["materia"] = self.materia.to_dict() if self.materia else None
                data["docente"] = self.docente.to_dict() if self.docente else None
                data["periodo"] = self.periodo.to_dict() if self.periodo else None
                data["horarios"] = [h.to_dict() for h in self.horarios] if self.horarios else []
                data["inscripciones"] = [i.to_dict() for i in self.inscripciones] if self.inscripciones else []
                return data

       
        class Modulo(db.Entity):
            id = PrimaryKey(int, auto=True)
            numero = Required(str)          
            nombre = Optional(str)         
            aulas = Set("Aula")             # contiene varias aulas
            def to_full_dict(self):
                data = self.to_dict()
                data["aulas"] = [a.to_dict() for a in self.aulas] if self.aulas else []
                return data

        class Aula(db.Entity):
            id = PrimaryKey(int, auto=True)
            numero = Required(str)          
            nombre = Optional(str)          
            modulo = Required(Modulo)      
            horarios = Set("Horario")      
            def to_full_dict(self):
                data = self.to_dict()
                data["modulo"] = self.modulo.to_dict() if self.modulo else None
                data["horarios"] = [h.to_dict() for h in self.horarios] if self.horarios else []
                return data 

        class Horario(db.Entity):
            id = PrimaryKey(int, auto=True)
            dia = Required(str)
            hora_inicio = Required(datetime.time)
            hora_fin = Required(datetime.time)
            grupo = Required(GrupoMateria)
            aula = Optional(Aula)
            def to_dict(self):
                return {
                    "id": self.id,
                    "dia": self.dia,
                    "hora_inicio": self.hora_inicio.strftime("%H:%M"),
                    "hora_fin": self.hora_fin.strftime("%H:%M"),
                    "grupo": self.grupo.id if self.grupo else None,
                    "aula": self.aula.to_dict() if self.aula else None
                }
            def to_full_dict(self):
                return {
                    "id": self.id,
                    "dia": self.dia,
                    "hora_inicio": self.hora_inicio.strftime("%H:%M"),
                    "hora_fin": self.hora_fin.strftime("%H:%M"),
                    "grupo": self.grupo.to_dict() if self.grupo else None,
                    "aula": self.aula.to_dict() if self.aula else None
                }

        class Estudiante(db.Entity):
            id = PrimaryKey(int, auto=True)
            registro = Required(str, unique=True)
            ci = Required(str, unique=True)
            nombre = Required(str)
            telefono = Optional(str)
            correo = Optional(str)
            otros = Optional(str)
            inscripciones = Set("Inscripcion")
            def to_full_dict(self):
                data = self.to_dict()
                data["inscripciones"] = [i.to_dict() for i in self.inscripciones] if self.inscripciones else []
                return data

        class Inscripcion(db.Entity):
            id = PrimaryKey(int, auto=True)
            fecha = Required(datetime.date)
            estudiante = Required(Estudiante)
            periodo = Required(Periodo)
            materias = Set("InscripcionMateria")
            
            def to_full_dict(self):
                data = self.to_dict()
                data["fecha"] = self.fecha.isoformat()
                data["estudiante"] = self.estudiante.to_dict() if self.estudiante else None
                data["periodo"] = self.periodo.to_full_dict() if self.periodo else None
                data["InscripcionMateria"] = [m.to_dict() for m in self.materias] if self.materias else []
                return data

        class InscripcionMateria(db.Entity):
            id = PrimaryKey(int, auto=True)
            inscripcion = Required(Inscripcion)
            grupo = Required(GrupoMateria)
            notas = Set("Nota")
            def to_full_dict(self):
                data = self.to_dict()
                data["inscripcion"] = self.inscripcion.to_full_dict() if self.inscripcion else None
                data["grupo"] = self.grupo.to_full_dict() if self.grupo else None
                data["notas"] = [n.to_dict() for n in self.notas] if self.notas else []
                return data

        class Nota(db.Entity):
            id = PrimaryKey(int, auto=True)
            nota = Required(float)
            inscripcion_materia = Required(InscripcionMateria)
            def to_full_dict(self):
                data = self.to_dict()
                data["inscripcion_materia"] = self.inscripcion_materia.to_full_dict() if self.inscripcion_materia else None
                return data
