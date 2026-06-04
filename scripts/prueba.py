from extras.scripts import Script, IntegerVar, StringVar, ObjectVar, ChoiceVar, BooleanVar
from dcim.models import Location, Site, Device, DeviceType, InventoryItem
# En v4.6.1 esta es la ruta interna exacta para los Roles unificados:
from extras.models import Role

class AutomatizarDespachoScript(Script):
    class Meta:
        name = "1. Automatizacion de Despachos"
        description = "Formulario para la creacion automatizada de despachos y activos."

    # --- CAMPOS DEL FORMULARIO ---
    sede = ObjectVar(model=Site, required=True, label="Sede / Sitio")
    planta = ObjectVar(model=Location, required=True, label="Planta", query_params={'site_id': '$sede'})
    num_despacho = StringVar(label="Nombre del Despacho")
    tomas_red = IntegerVar(default=2, label="Tomas RJ45")
    
    tipo_pc = ChoiceVar(choices=(('torre', 'Torre'), ('portatil', 'Portatil')), default='torre', label="Tipo de PC")
    num_pcs = IntegerVar(default=1, label="Cantidad de PCs")
    num_pantallas = IntegerVar(default=1, label="Cantidad de Pantallas")
    docking_station = BooleanVar(default=False, label="Lleva Docking Station")
    poner_telefono = BooleanVar(default=True, label="Anadir Telefono IP")
    
    num_impresoras_red = IntegerVar(default=0, label="Impresoras de Red")
    num_impresoras_usb = IntegerVar(default=0, label="Impresoras USB")
    num_teclados = IntegerVar(default=1, label="Teclados")
    num_ratones = IntegerVar(default=1, label="Ratones")
    sai_local = BooleanVar(default=False, label="Tiene SAI de suelo")

    def run(self, data, commit):
        sede_obj = data['sede']
        planta_obj = data['planta']
        despacho_name = data['num_despacho']
        despacho_slug = despacho_name.lower().replace(" ", "-")

        # 1. Crear Ubicación
        despacho = Location(
            name=despacho_name,
            slug=f"{planta_obj.slug}-{despacho_slug}",
            site=sede_obj,
            parent=planta_obj,
            status='active'
        )
        despacho.save()
        self.log_success(f"Ubicacion creada: {despacho_name}")

        # 2. Roles y Modelos
        rol_pc, _ = Role.objects.get_or_create(name="Puesto de Usuario", slug="puesto-usuario", color="20c997")
        rol_imp, _ = Role.objects.get_or_create(name="Impresora", slug="impresora", color="007bff")
        rol_tel, _ = Role.objects.get_or_create(name="Telefonia", slug="telefonia", color="9c27b0")
        
        type_pc, _ = DeviceType.objects.get_or_create(model=f"PC {data['tipo_pc'].capitalize()} Generico", slug=f"pc-{data['tipo_pc']}-gen", manufacturer_id=1)
        type_imp, _ = DeviceType.objects.get_or_create(model="Impresora Generica", slug="impresora-generica", manufacturer_id=1)
        type_tel, _ = DeviceType.objects.get_or_create(model="8018 Deskphone", slug="alcatel-lucent-8018-deskphone", manufacturer_id=1)

        # 3. Dispositivos (PCs)
        for i in range(1, data['num_pcs'] + 1):
            pc = Device(name=f"PC-{despacho_slug}-{i}".upper(), device_type=type_pc, role=rol_pc, site=sede_obj, location=despacho, status='active')
            pc.save()
            self.log_success(f"PC creado: {pc.name}")

        # 4. Teléfono IP
        if data['poner_telefono']:
            tel = Device(name=f"TEL-{despacho_slug}".upper(), device_type=type_tel, role=rol_tel, site=sede_obj, location=despacho, status='active')
            tel.save()
            self.log_success(f"Telefono creado: {tel.name}")

        # 5. Impresoras de Red
        for i in range(1, data['num_impresoras_red'] + 1):
            imp = Device(name=f"IMP-RED-{despacho_slug}-{i}".upper(), device_type=type_imp, role=rol_imp, site=sede_obj, location=despacho, status='active')
            imp.save()
            self.log_success(f"Impresora de red creada: {imp.name}")

        # 6. Inventario de Periféricos
        equipo_ref = Device.objects.filter(location=despacho).first()
        items_inventario = [
            ("Tomas RJ45", data['tomas_red']),
            ("Monitores", data['num_pantallas']),
            ("Impresoras USB", data['num_impresoras_usb']),
            ("Teclados", data['num_teclados']),
            ("Ratones", data['num_ratones']),
        ]
        if data['docking_station']: items_inventario.append(("Docking Station", data['num_pcs']))
        if data['sai_local']: items_inventario.append(("SAI Local", 1))

        for nombre_item, cantidad in items_inventario:
            if cantidad > 0:
                for c in range(1, cantidad + 1):
                    InventoryItem(name=f"{nombre_item} {c}", label=f"Inventario {despacho_name}", device=equipo_ref).save()
                self.log_success(f"Inventario registrado: {cantidad} x {nombre_item}")
