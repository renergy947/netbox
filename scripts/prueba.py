from extras.scripts import Script, IntegerVar, StringVar, ObjectVar, ChoiceVar, BooleanVar
from dcim.models import Location, Site, Device, DeviceType, InventoryItem
from extras.models import Role

class AutomatizarDespachoScript(Script):
    class Meta:
        name = "1. Automatización de Despachos"
        description = "Formulario oficial para la creación masiva y estructurada de despachos en planta y activos de usuario."

    # --- VARIABLES DE ENTRADA (Mapeadas según la documentación oficial) ---
    sede = ObjectVar(
        model=Site,
        required=True,
        label="Sede / Sitio",
        description="Selecciona la sede física de la organización"
    )
    planta = ObjectVar(
        model=Location,
        required=True,
        label="Planta",
        query_params={'site_id': '$sede'},
        description="Selecciona la planta (Ubicación jerárquica principal)"
    )
    num_despacho = StringVar(
        label="Nombre/Número del Despacho",
        description="Identificador para el nuevo espacio (ej: Despacho 101, Dirección)"
    )
    tomas_red = IntegerVar(
        default=2,
        label="Tomas RJ45 de pared",
        description="Número de puntos físicos de red en el perímetro"
    )
    tipo_pc = ChoiceVar(
        choices=(
            ('torre', 'Ordenador de Torre'),
            ('portatil', 'Ordenador Portátil')
        ),
        default='torre',
        label="Tipo de PC principal",
        description="Factor de forma del equipamiento informático básico"
    )
    num_pcs = IntegerVar(
        default=1,
        label="Cantidad de PCs",
        description="Número de ordenadores a desplegar"
    )
    num_pantallas = IntegerVar(
        default=1,
        label="Cantidad de Pantallas",
        description="Monitores auxiliares o principales del puesto"
    )
    docking_station = BooleanVar(
        default=False,
        label="¿Incluye Docking Station?",
        description="Replicador de puertos para portátiles"
    )
    poner_telefono = BooleanVar(
        default=True,
        label="¿Añadir Teléfono IP de mesa?",
        description="Despliega terminal de voz corporativo"
    )
    num_impresoras_red = IntegerVar(
        default=0,
        label="Impresoras de Red",
        description="Impresoras corporativas cableadas al switch"
    )
    num_impresoras_usb = IntegerVar(
        default=0,
        label="Impresoras USB locales",
        description="Equipos de impresión directa conectados a PC"
    )
    num_teclados = IntegerVar(
        default=1,
        label="Teclados USB"
    )
    num_ratones = IntegerVar(
        default=1,
        label="Ratones USB"
    )
    sai_local = BooleanVar(
        default=False,
        label="¿Tiene SAI de suelo?",
        description="Sistema de alimentación ininterrumpida local"
    )

    def run(self, data, commit):
        # Desempaquetado seguro de los objetos del formulario
        sede_obj = data['sede']
        planta_obj = data['planta']
        despacho_name = data['num_despacho']
        
        # Generar un slug limpio y amigable
        despacho_slug = despacho_name.lower().replace(" ", "-")

        # 1. Instanciación del modelo Location (Despacho como hijo de Planta)
        despacho = Location(
            name=despacho_name,
            slug=f"{planta_obj.slug}-{despacho_slug}",
            site=sede_obj,
            parent=planta_obj,
            status='active'
        )
        despacho.save()
        self.log_success(f"Ubicación creada con éxito: {despacho_name}")

        # 2. Búsqueda o creación de Roles de Dispositivo (Uso del objeto Role de extras)
        rol_pc, _ = Role.objects.get_or_create(name="Puesto de Usuario", slug="puesto-usuario", color="20c997")
        rol_imp, _ = Role.objects.get_or_create(name="Impresora", slug="impresora", color="007bff")
        rol_tel, _ = Role.objects.get_or_create(name="Telefonía", slug="telefonia", color="9c27b0")
        
        # Búsqueda o creación de Modelos (DeviceTypes) genéricos
        type_pc, _ = DeviceType.objects.get_or_create(
            model=f"PC {data['tipo_pc'].capitalize()} Genérico", 
            slug=f"pc-{data['tipo_pc']}-gen", 
            manufacturer_id=1
        )
        type_imp, _ = DeviceType.objects.get_or_create(model="Impresora Genérica", slug="impresora-generica", manufacturer_id=1)
        type_tel, _ = DeviceType.objects.get_or_create(model="8018 Deskphone", slug="alcatel-lucent-8018-deskphone", manufacturer_id=1)

        # 3. Creación automatizada de Equipos de Escritorio
        for i in range(1, data['num_pcs'] + 1):
            pc = Device(
                name=f"PC-{despacho_slug}-{i}".upper(),
                device_type=type_pc,
                role=rol_pc,
                site=sede_obj,
                location=despacho,
                status='active'
            )
            pc.save()
            self.log_success(f"Dispositivo de cómputo registrado: {pc.name}")

        # 4. Creación automatizada de Terminal de Telefonía IP
        if data['poner_telefono']:
            tel = Device(
                name=f"TEL-{despacho_slug}".upper(),
                device_type=type_tel,
                role=rol_tel,
                site=sede_obj,
                location=despacho,
                status='active'
            )
            tel.save()
            self.log_success(f"Terminal telefónico asignado: {tel.name}")

        # 5. Creación de Impresoras de Red
        for i in range(1, data['num_impresoras_red'] + 1):
            imp = Device(
                name=f"IMP-RED-{despacho_slug}-{i}".upper(),
                device_type=type_imp,
                role=rol_imp,
                site=sede_obj,
                location=despacho,
                status='active'
            )
            imp.save()
            self.log_success(f"Impresora de red registrada: {imp.name}")

        # 6. Módulo de Inventario Auxiliar (Periféricos no administrados en red)
        # Se asocian al primer dispositivo del despacho como pide el ORM de NetBox
        equipo_referencia = Device.objects.filter(location=despacho).first()
        
        elementos_inventario = [
            ("Tomas RJ45", data['tomas_red']),
            ("Monitores/Pantallas", data['num_pantallas']),
            ("Impresoras USB", data['num_impresoras_usb']),
            ("Teclados USB", data['num_teclados']),
            ("Ratones USB", data['num_ratones']),
        ]
        
        if data['docking_station']:
            elementos_inventario.append(("Docking Station", data['num_pcs']))
        if data['sai_local']:
            elementos_inventario.append(("SAI Local Puesto", 1))

        for nombre_item, cantidad in elementos_inventario:
            if cantidad > 0:
                for c in range(1, cantidad + 1):
                    InventoryItem(
                        name=f"{nombre_item} {c}",
                        label=f"Inventario {despacho_name}",
                        device=equipo_referencia
                    ).save()
                self.log_success(f"Componentes indexados: {cantidad} x {nombre_item}")
