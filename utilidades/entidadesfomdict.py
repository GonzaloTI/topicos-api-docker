from pony.orm import select
import datetime

# Carrera
class Carrera(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar planes (Set relationship) - sacar del dict principal
        planes_data = data_copy.pop('planes', [])
        
        # Crear la carrera base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        carrera = cls(**valid_fields)
        
        # Agregar planes después de crear la carrera
        for plan_data in planes_data:
            if isinstance(plan_data, dict):
                plan_data_copy = plan_data.copy()
                plan_data_copy['carrera'] = carrera
                PlanDeEstudio.from_dict(plan_data_copy) if hasattr(PlanDeEstudio, 'from_dict') else PlanDeEstudio(**plan_data_copy)
            elif isinstance(plan_data, int):
                plan = PlanDeEstudio[plan_data]
                carrera.planes.add(plan)
        
        return carrera

# PlanDeEstudio
class PlanDeEstudio(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar fecha si viene como string ISO
        if 'fecha' in data_copy and isinstance(data_copy['fecha'], str):
            data_copy['fecha'] = datetime.datetime.fromisoformat(data_copy['fecha']).date()
        
        # Manejar carrera (Required relationship)
        if 'carrera' in data_copy and isinstance(data_copy['carrera'], dict):
            carrera_data = data_copy.pop('carrera')
            existing_carrera = select(c for c in Carrera if c.codigo == carrera_data.get('codigo')).first()
            if existing_carrera:
                data_copy['carrera'] = existing_carrera
            else:
                data_copy['carrera'] = Carrera.from_dict(carrera_data) if hasattr(Carrera, 'from_dict') else Carrera(**carrera_data)
        elif 'carrera_id' in data_copy:
            data_copy['carrera'] = Carrera[data_copy.pop('carrera_id')]
        
        # Manejar materias (Set relationship)
        materias_data = data_copy.pop('materias', [])
        
        # Crear el plan base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        plan = cls(**valid_fields)
        
        # Agregar materias después de crear el plan
        for materia_data in materias_data:
            if isinstance(materia_data, dict):
                materia_data_copy = materia_data.copy()
                materia_data_copy['plan'] = plan
                Materia.from_dict(materia_data_copy) if hasattr(Materia, 'from_dict') else Materia(**materia_data_copy)
            elif isinstance(materia_data, int):
                materia = Materia[materia_data]
                plan.materias.add(materia)
        
        return plan

# Nivel
class Nivel(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar materias (Set relationship)
        materias_data = data_copy.pop('materias', [])
        
        # Crear el nivel base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        nivel = cls(**valid_fields)
        
        # Agregar materias después de crear el nivel
        for materia_data in materias_data:
            if isinstance(materia_data, dict):
                materia_data_copy = materia_data.copy()
                materia_data_copy['nivel'] = nivel
                Materia.from_dict(materia_data_copy) if hasattr(Materia, 'from_dict') else Materia(**materia_data_copy)
            elif isinstance(materia_data, int):
                materia = Materia[materia_data]
                nivel.materias.add(materia)
        
        return nivel

# Docente
class Docente(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar grupos (Set relationship)
        grupos_data = data_copy.pop('grupos', [])
        
        # Crear el docente base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        docente = cls(**valid_fields)
        
        # Agregar grupos después de crear el docente
        for grupo_data in grupos_data:
            if isinstance(grupo_data, dict):
                grupo_data_copy = grupo_data.copy()
                grupo_data_copy['docente'] = docente
                GrupoMateria.from_dict(grupo_data_copy) if hasattr(GrupoMateria, 'from_dict') else GrupoMateria(**grupo_data_copy)
            elif isinstance(grupo_data, int):
                grupo = GrupoMateria[grupo_data]
                docente.grupos.add(grupo)
        
        return docente

# Gestion
class Gestion(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar periodos (Set relationship)
        periodos_data = data_copy.pop('periodos', [])
        
        # Crear la gestión base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        gestion = cls(**valid_fields)
        
        # Agregar periodos después de crear la gestión
        for periodo_data in periodos_data:
            if isinstance(periodo_data, dict):
                periodo_data_copy = periodo_data.copy()
                periodo_data_copy['gestion'] = gestion
                Periodo.from_dict(periodo_data_copy) if hasattr(Periodo, 'from_dict') else Periodo(**periodo_data_copy)
            elif isinstance(periodo_data, int):
                periodo = Periodo[periodo_data]
                gestion.periodos.add(periodo)
        
        return gestion

# TipoPeriodo
class TipoPeriodo(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar periodos (Set relationship)
        periodos_data = data_copy.pop('periodos', [])
        
        # Crear el tipo de periodo base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        tipo_periodo = cls(**valid_fields)
        
        # Agregar periodos después de crear el tipo periodo
        for periodo_data in periodos_data:
            if isinstance(periodo_data, dict):
                periodo_data_copy = periodo_data.copy()
                periodo_data_copy['tipoperiodo'] = tipo_periodo
                Periodo.from_dict(periodo_data_copy) if hasattr(Periodo, 'from_dict') else Periodo(**periodo_data_copy)
            elif isinstance(periodo_data, int):
                periodo = Periodo[periodo_data]
                tipo_periodo.periodos.add(periodo)
        
        return tipo_periodo

# Periodo
class Periodo(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar gestion (Required relationship)
        if 'gestion' in data_copy and isinstance(data_copy['gestion'], dict):
            gestion_data = data_copy.pop('gestion')
            existing_gestion = select(g for g in Gestion if g.anio == gestion_data.get('anio')).first()
            if existing_gestion:
                data_copy['gestion'] = existing_gestion
            else:
                data_copy['gestion'] = Gestion.from_dict(gestion_data) if hasattr(Gestion, 'from_dict') else Gestion(**gestion_data)
        elif 'gestion_id' in data_copy:
            data_copy['gestion'] = Gestion[data_copy.pop('gestion_id')]
        
        # Manejar tipoperiodo (Required relationship)
        if 'tipoperiodo' in data_copy and isinstance(data_copy['tipoperiodo'], dict):
            tipo_data = data_copy.pop('tipoperiodo')
            existing_tipo = select(t for t in TipoPeriodo if t.nombre == tipo_data.get('nombre')).first()
            if existing_tipo:
                data_copy['tipoperiodo'] = existing_tipo
            else:
                data_copy['tipoperiodo'] = TipoPeriodo.from_dict(tipo_data) if hasattr(TipoPeriodo, 'from_dict') else TipoPeriodo(**tipo_data)
        elif 'tipoperiodo_id' in data_copy:
            data_copy['tipoperiodo'] = TipoPeriodo[data_copy.pop('tipoperiodo_id')]
        
        # Manejar Set relationships
        inscripciones_data = data_copy.pop('inscripciones', [])
        grupos_data = data_copy.pop('grupos', [])
        
        # Crear el periodo base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        periodo = cls(**valid_fields)
        
        # Agregar inscripciones y grupos después
        for inscripcion_data in inscripciones_data:
            if isinstance(inscripcion_data, dict):
                inscripcion_data_copy = inscripcion_data.copy()
                inscripcion_data_copy['periodo'] = periodo
                Inscripcion.from_dict(inscripcion_data_copy) if hasattr(Inscripcion, 'from_dict') else Inscripcion(**inscripcion_data_copy)
            elif isinstance(inscripcion_data, int):
                inscripcion = Inscripcion[inscripcion_data]
                periodo.inscripciones.add(inscripcion)
        
        for grupo_data in grupos_data:
            if isinstance(grupo_data, dict):
                grupo_data_copy = grupo_data.copy()
                grupo_data_copy['periodo'] = periodo
                GrupoMateria.from_dict(grupo_data_copy) if hasattr(GrupoMateria, 'from_dict') else GrupoMateria(**grupo_data_copy)
            elif isinstance(grupo_data, int):
                grupo = GrupoMateria[grupo_data]
                periodo.grupos.add(grupo)
        
        return periodo

# GrupoMateria
class GrupoMateria(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar materia (Required relationship)
        if 'materia' in data_copy and isinstance(data_copy['materia'], dict):
            materia_data = data_copy.pop('materia')
            existing_materia = select(m for m in Materia if m.sigla == materia_data.get('sigla')).first()
            if existing_materia:
                data_copy['materia'] = existing_materia
            else:
                data_copy['materia'] = Materia.from_dict(materia_data) if hasattr(Materia, 'from_dict') else Materia(**materia_data)
        elif 'materia_id' in data_copy:
            data_copy['materia'] = Materia[data_copy.pop('materia_id')]
        
        # Manejar docente (Required relationship)
        if 'docente' in data_copy and isinstance(data_copy['docente'], dict):
            docente_data = data_copy.pop('docente')
            existing_docente = select(d for d in Docente if d.registro == docente_data.get('registro')).first()
            if existing_docente:
                data_copy['docente'] = existing_docente
            else:
                data_copy['docente'] = Docente.from_dict(docente_data) if hasattr(Docente, 'from_dict') else Docente(**docente_data)
        elif 'docente_id' in data_copy:
            data_copy['docente'] = Docente[data_copy.pop('docente_id')]
        
        # Manejar periodo (Required relationship)
        if 'periodo' in data_copy and isinstance(data_copy['periodo'], dict):
            periodo_data = data_copy.pop('periodo')
            existing_periodo = select(p for p in Periodo if p.numero == periodo_data.get('numero')).first()
            if existing_periodo:
                data_copy['periodo'] = existing_periodo
            else:
                data_copy['periodo'] = Periodo.from_dict(periodo_data) if hasattr(Periodo, 'from_dict') else Periodo(**periodo_data)
        elif 'periodo_id' in data_copy:
            data_copy['periodo'] = Periodo[data_copy.pop('periodo_id')]
        
        # Manejar Set relationships
        horarios_data = data_copy.pop('horarios', [])
        inscripciones_data = data_copy.pop('inscripciones', [])
        
        # Crear el grupo base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        grupo = cls(**valid_fields)
        
        # Agregar horarios e inscripciones después
        for horario_data in horarios_data:
            if isinstance(horario_data, dict):
                horario_data_copy = horario_data.copy()
                horario_data_copy['grupo'] = grupo
                Horario.from_dict(horario_data_copy) if hasattr(Horario, 'from_dict') else Horario(**horario_data_copy)
            elif isinstance(horario_data, int):
                horario = Horario[horario_data]
                grupo.horarios.add(horario)
        
        for inscripcion_data in inscripciones_data:
            if isinstance(inscripcion_data, dict):
                inscripcion_data_copy = inscripcion_data.copy()
                inscripcion_data_copy['grupo'] = grupo
                InscripcionMateria.from_dict(inscripcion_data_copy) if hasattr(InscripcionMateria, 'from_dict') else InscripcionMateria(**inscripcion_data_copy)
            elif isinstance(inscripcion_data, int):
                inscripcion = InscripcionMateria[inscripcion_data]
                grupo.inscripciones.add(inscripcion)
        
        return grupo

# Modulo
class Modulo(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar aulas (Set relationship)
        aulas_data = data_copy.pop('aulas', [])
        
        # Crear el módulo base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        modulo = cls(**valid_fields)
        
        # Agregar aulas después de crear el módulo
        for aula_data in aulas_data:
            if isinstance(aula_data, dict):
                aula_data_copy = aula_data.copy()
                aula_data_copy['modulo'] = modulo
                Aula.from_dict(aula_data_copy) if hasattr(Aula, 'from_dict') else Aula(**aula_data_copy)
            elif isinstance(aula_data, int):
                aula = Aula[aula_data]
                modulo.aulas.add(aula)
        
        return modulo

# Aula
class Aula(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar modulo (Required relationship)
        if 'modulo' in data_copy and isinstance(data_copy['modulo'], dict):
            modulo_data = data_copy.pop('modulo')
            existing_modulo = select(m for m in Modulo if m.numero == modulo_data.get('numero')).first()
            if existing_modulo:
                data_copy['modulo'] = existing_modulo
            else:
                data_copy['modulo'] = Modulo.from_dict(modulo_data) if hasattr(Modulo, 'from_dict') else Modulo(**modulo_data)
        elif 'modulo_id' in data_copy:
            data_copy['modulo'] = Modulo[data_copy.pop('modulo_id')]
        
        # Manejar horarios (Set relationship)
        horarios_data = data_copy.pop('horarios', [])
        
        # Crear el aula base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        aula = cls(**valid_fields)
        
        # Agregar horarios después de crear el aula
        for horario_data in horarios_data:
            if isinstance(horario_data, dict):
                horario_data_copy = horario_data.copy()
                horario_data_copy['aula'] = aula
                Horario.from_dict(horario_data_copy) if hasattr(Horario, 'from_dict') else Horario(**horario_data_copy)
            elif isinstance(horario_data, int):
                horario = Horario[horario_data]
                aula.horarios.add(horario)
        
        return aula

# Horario
class Horario(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar conversión de horas si vienen como strings
        if 'hora_inicio' in data_copy and isinstance(data_copy['hora_inicio'], str):
            data_copy['hora_inicio'] = datetime.datetime.strptime(data_copy['hora_inicio'], "%H:%M").time()
        
        if 'hora_fin' in data_copy and isinstance(data_copy['hora_fin'], str):
            data_copy['hora_fin'] = datetime.datetime.strptime(data_copy['hora_fin'], "%H:%M").time()
        
        # Manejar grupo (Required relationship)
        if 'grupo' in data_copy and isinstance(data_copy['grupo'], dict):
            grupo_data = data_copy.pop('grupo')
            existing_grupo = select(g for g in GrupoMateria if g.grupo == grupo_data.get('grupo')).first()
            if existing_grupo:
                data_copy['grupo'] = existing_grupo
            else:
                data_copy['grupo'] = GrupoMateria.from_dict(grupo_data) if hasattr(GrupoMateria, 'from_dict') else GrupoMateria(**grupo_data)
        elif 'grupo_id' in data_copy:
            data_copy['grupo'] = GrupoMateria[data_copy.pop('grupo_id')]
        
        # Manejar aula (Optional relationship)
        if 'aula' in data_copy and isinstance(data_copy['aula'], dict):
            aula_data = data_copy.pop('aula')
            existing_aula = select(a for a in Aula if a.numero == aula_data.get('numero')).first()
            if existing_aula:
                data_copy['aula'] = existing_aula
            else:
                data_copy['aula'] = Aula.from_dict(aula_data) if hasattr(Aula, 'from_dict') else Aula(**aula_data)
        elif 'aula_id' in data_copy:
            data_copy['aula'] = Aula[data_copy.pop('aula_id')]
        
        # Crear el horario
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        return cls(**valid_fields)

# Estudiante
class Estudiante(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar inscripciones (Set relationship)
        inscripciones_data = data_copy.pop('inscripciones', [])
        
        # Crear el estudiante base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        estudiante = cls(**valid_fields)
        
        # Agregar inscripciones después de crear el estudiante
        for inscripcion_data in inscripciones_data:
            if isinstance(inscripcion_data, dict):
                inscripcion_data_copy = inscripcion_data.copy()
                inscripcion_data_copy['estudiante'] = estudiante
                Inscripcion.from_dict(inscripcion_data_copy) if hasattr(Inscripcion, 'from_dict') else Inscripcion(**inscripcion_data_copy)
            elif isinstance(inscripcion_data, int):
                inscripcion = Inscripcion[inscripcion_data]
                estudiante.inscripciones.add(inscripcion)
        
        return estudiante

# Inscripcion
class Inscripcion(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar fecha si viene como string ISO
        if 'fecha' in data_copy and isinstance(data_copy['fecha'], str):
            data_copy['fecha'] = datetime.datetime.fromisoformat(data_copy['fecha']).date()
        
        # Manejar estudiante (Required relationship)
        if 'estudiante' in data_copy and isinstance(data_copy['estudiante'], dict):
            estudiante_data = data_copy.pop('estudiante')
            existing_estudiante = select(e for e in Estudiante if e.registro == estudiante_data.get('registro')).first()
            if existing_estudiante:
                data_copy['estudiante'] = existing_estudiante
            else:
                data_copy['estudiante'] = Estudiante.from_dict(estudiante_data) if hasattr(Estudiante, 'from_dict') else Estudiante(**estudiante_data)
        elif 'estudiante_id' in data_copy:
            data_copy['estudiante'] = Estudiante[data_copy.pop('estudiante_id')]
        
        # Manejar periodo (Required relationship)
        if 'periodo' in data_copy and isinstance(data_copy['periodo'], dict):
            periodo_data = data_copy.pop('periodo')
            existing_periodo = select(p for p in Periodo if p.numero == periodo_data.get('numero')).first()
            if existing_periodo:
                data_copy['periodo'] = existing_periodo
            else:
                data_copy['periodo'] = Periodo.from_dict(periodo_data) if hasattr(Periodo, 'from_dict') else Periodo(**periodo_data)
        elif 'periodo_id' in data_copy:
            data_copy['periodo'] = Periodo[data_copy.pop('periodo_id')]
        
        # Manejar materias (Set relationship)
        materias_data = data_copy.pop('materias', [])
        
        # Crear la inscripción base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        inscripcion = cls(**valid_fields)
        
        # Agregar materias después de crear la inscripción
        for materia_data in materias_data:
            if isinstance(materia_data, dict):
                materia_data_copy = materia_data.copy()
                materia_data_copy['inscripcion'] = inscripcion
                InscripcionMateria.from_dict(materia_data_copy) if hasattr(InscripcionMateria, 'from_dict') else InscripcionMateria(**materia_data_copy)
            elif isinstance(materia_data, int):
                materia = InscripcionMateria[materia_data]
                inscripcion.materias.add(materia)
        
        return inscripcion

# InscripcionMateria
class InscripcionMateria(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar inscripcion (Required relationship)
        if 'inscripcion' in data_copy and isinstance(data_copy['inscripcion'], dict):
            inscripcion_data = data_copy.pop('inscripcion')
            # No hay un campo único claro para buscar, se podría usar combinación de campos
            data_copy['inscripcion'] = Inscripcion.from_dict(inscripcion_data) if hasattr(Inscripcion, 'from_dict') else Inscripcion(**inscripcion_data)
        elif 'inscripcion_id' in data_copy:
            data_copy['inscripcion'] = Inscripcion[data_copy.pop('inscripcion_id')]
        
        # Manejar grupo (Required relationship)
        if 'grupo' in data_copy and isinstance(data_copy['grupo'], dict):
            grupo_data = data_copy.pop('grupo')
            existing_grupo = select(g for g in GrupoMateria if g.grupo == grupo_data.get('grupo')).first()
            if existing_grupo:
                data_copy['grupo'] = existing_grupo
            else:
                data_copy['grupo'] = GrupoMateria.from_dict(grupo_data) if hasattr(GrupoMateria, 'from_dict') else GrupoMateria(**grupo_data)
        elif 'grupo_id' in data_copy:
            data_copy['grupo'] = GrupoMateria[data_copy.pop('grupo_id')]
        
        # Manejar notas (Set relationship)
        notas_data = data_copy.pop('notas', [])
        
        # Crear la inscripción materia base
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        inscripcion_materia = cls(**valid_fields)
        
        # Agregar notas después de crear la inscripción materia
        for nota_data in notas_data:
            if isinstance(nota_data, dict):
                nota_data_copy = nota_data.copy()
                nota_data_copy['inscripcionmateria'] = inscripcion_materia
                Nota.from_dict(nota_data_copy) if hasattr(Nota, 'from_dict') else Nota(**nota_data_copy)
            elif isinstance(nota_data, int):
                nota = Nota[nota_data]
                inscripcion_materia.notas.add(nota)
        
        return inscripcion_materia

# Nota
class Nota(db.Entity):
    # ... campos existentes ...
    
    @classmethod
    def from_dict(cls, data_dict):
        data_copy = data_dict.copy()
        
        # Manejar inscripcionmateria (Required relationship)
        if 'inscripcionmateria' in data_copy and isinstance(data_copy['inscripcionmateria'], dict):
            inscripcion_data = data_copy.pop('inscripcionmateria')
            data_copy['inscripcionmateria'] = InscripcionMateria.from_dict(inscripcion_data) if hasattr(InscripcionMateria, 'from_dict') else InscripcionMateria(**inscripcion_data)
        elif 'inscripcionmateria_id' in data_copy:
            data_copy['inscripcionmateria'] = InscripcionMateria[data_copy.pop('inscripcionmateria_id')]
        
        # Crear la nota
        valid_fields = {key: value for key, value in data_copy.items() 
                       if hasattr(cls, key)}
        return cls(**valid_fields)