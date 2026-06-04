from extras.scripts import Script, IntegerVar, StringVar, ObjectVar, ChoiceVar, BooleanVar
from dcim.models import Location, Site, Device, DeviceType, InventoryItem
from extras.models import Role

class AutomatizarDespacho46(Script):
    class Meta:
        name = "1. Automatización de Despachos (v4.6.x)"
        description = "Formulario dinámico con desplegables interactivos para NetBox 4.6.1."

    # --- DESPLEGABLES DINÁMICOS NATIVOS v4.6 ---
    sede = ObjectVar(
        model=Site,
        required=True,
        label="Sede / Sitio",
        description="Selecciona la Sede donde se ubica el despacho"
    )
    planta = ObjectVar(
        model=Location,
        required=True,
        label="Planta del edificio",
        query_params={
            'site_id': '$sede'  # Vinculación dinámica nativa en v4.6
        },
        description="Selecciona la planta correspondiente"
    )

    # --- DATOS DEL DESPACHO ---
    num_despacho = StringVar(
        label="Nombre del Despacho",
        description="Ejemplo: Despacho 104 u Oficina Técnica"
    )
    tomas_red = IntegerVar(
        default=2,
        label="Tomas RJ45",
        description="Número de tomas de red en las paredes"
    )

    # --- EQUIPAMIENTO DEL PUESTO ---
    tipo_pc = ChoiceVar(
        choices=(
            ('torre', 'Ordenador de Torre'),
            ('portatil', 'Ordenador Portátil')
        ),
        default='torre',
        label="Tipo de PC"
    )
    num_pcs = IntegerVar(default=1, label="Cantidad de PCs")
    num_pantallas = IntegerVar(default=1, label="Monitores/Pantallas")
    docking_station = BooleanVar(default=False, label="¿Lleva Docking Station?")
    poner_telefono = BooleanVar(default=True, label="¿Añadir Teléfono IP?")
    
    # --- IMPRESIÓN Y PERIFÉRICOS ---
    num_impresoras_red = IntegerVar(default=0, label="Impresoras de Red")
    num_impresoras_usb = IntegerVar(default=0, label="Impresoras USB locales")
    num_teclados = IntegerVar(default=1, label="Teclados")
    num_ratones = IntegerVar(default=1, label="Ratones")
    sai_local = BooleanVar(default=False, label="¿Tiene SAI de suelo?")

    def run(self, data, commit):
        sede_obj = data['sede']
        planta_obj = data['planta']
        despacho_name = data['num_despacho']
        despacho_slug = despacho_name.lower().replace(" ", "-")

        # 1. Crear el Despacho (Ubicación hija)
        despacho = Location(
            name=despacho_name,
            slug=f"{planta_obj.slug}-{despacho_slug}",
            site=sede_obj,
            parent=planta_obj,
            status='active'
        )
        despacho.save()
        self.log_success(f"Creado el despacho: {despacho_name} en {sede_obj.name} -> {planta_obj.name}")

        # En NetBox 4.x los Roles ya no son DeviceRole, se unificaron en extras.Role
        rol_pc, _ = Role.objects.get_or_create(name="Puesto de Usuario", slug="puesto-usuario", color="20c997")
        rol_imp, _ = Role.objects.get_or_create(name="Impresora", slug="impresora", color="007bff")
        rol_tel, _ = Role.objects.get_or_create(name="Telefonía", slug="telefonia", color="9c27b0")
        
        # Tipos de dispositivo (Modelos) genéricos
        type_pc, _ = DeviceType.objects.get_or_create(model=f"PC {data['tipo_pc'].capitalize()} Genérico", slug=f"pc-{data['tipo_pc']}-gen", manufacturer_id=1)
        type_imp, _ = DeviceType.objects.get_or_create(model="Impresora Genérica", slug="impresora-generica", manufacturer_id=1)
        type_tel, _ = DeviceType.objects.get_or_create(model="8018 Deskphone", slug="alcatel-lucent-8018-deskphone", manufacturer_id=1)

        # 2. Crear los Ordenadores
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
            self.log_success(f"Dispositivo creado: {pc.name}")

        # 3. Crear Teléfono IP
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
            self.log_success(f"Teléfono IP creado: {tel.name}")

        # 4. Crear Impresoras de Red
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
            self.log_success(f"Impresora de Red creada: {imp.name}")

        # 5. Inventario de Periféricos asociados al primer equipo del despacho
        equipo_ref = Device.objects.filter(location=despacho).first()
        
        items_inventario = [
            ("Tomas de pared RJ45", data['tomas_red']),
            ("Monitores/Pantallas", data['num_pantallas']),
            ("Impresoras USB locales", data['num_impresoras_usb']),
            ("Teclados USB", data['num_teclados']),
            ("Ratones USB", data['num_ratones']),
        ]
        
        if data['docking_station']:
            items_inventario.append(("Docking Station", data['num_pcs']))
        if data['sai_local']:
            items_inventario.append(("SAI Local Puesto", 1))

        for nombre_item, cantidad in items_inventario:
            if cantidad > 0:
                for c in range(1, cantidad + 1):
                    inv_item = InventoryItem(
                        name=f"{nombre_item} {c}",
                        label=f"Inventario {despacho_name}",
                        device=equipo_ref
                    )
                    inv_item.save()
                self.log_success(f"Registrado en inventario: {cantidad} x {nombre_item}")