from extras.scripts import Script, ObjectVar
from dcim.models import Device, Region, SiteGroup, Site, Location, DeviceRole

class InformeGlobalDispositivos(Script):
    class Meta:
        name = "Informe Avanzado de Dispositivos"
        description = "Muestra activos filtrados por criterios geográficos opcionales y agrupados por su función (Rol)."

    # --- FILTROS NO RESTRICTIVOS (Todos required=False) ---
    region = ObjectVar(
        model=Region,
        required=False,
        label="Región",
        description="Opcional: Filtrar por región geográfica"
    )
    site_group = ObjectVar(
        model=SiteGroup,
        required=False,
        label="Grupo de Sitios",
        description="Opcional: Filtrar por grupo organizativo de sedes"
    )
    site = ObjectVar(
        model=Site,
        required=False,
        label="Sitio / Sede",
        query_params={'region_id': '$region', 'group_id': '$site_group'},
        description="Opcional: Filtrar por una sede específica"
    )
    location = ObjectVar(
        model=Location,
        required=False,
        label="Ubicación específica",
        query_params={'site_id': '$site'},
        description="Opcional: Filtrar por un despacho, planta o cuarto técnico"
    )

    def run(self, data, commit):
        # Comenzamos con el universo completo de dispositivos de la BD
        dispositivos = Device.objects.all()

        # Aplicación dinámica de filtros según lo que elijas en la web
        if data['region']:
            dispositivos = dispositivos.filter(site__region=data['region'])
            self.log_info(f"Filtrando por Región: {data['region'].name}")
            
        if data['site_group']:
            dispositivos = dispositivos.filter(site__group=data['site_group'])
            self.log_info(f"Filtrando por Grupo de Sitios: {data['site_group'].name}")
            
        if data['site']:
            dispositivos = dispositivos.filter(site=data['site'])
            self.log_info(f"Filtrando por Sitio: {data['site'].name}")
            
        if data['location']:
            dispositivos = dispositivos.filter(location=data['location'])
            self.log_info(f"Filtrando por Ubicación: {data['location'].name}")

        if not dispositivos.exists():
            self.log_warning("No se han encontrado dispositivos que cumplan los criterios seleccionados.")
            return

        # --- AGRUPACIÓN POR FUNCIÓN DEL DISPOSITIVO (ROLE) ---
        grupos_por_funcion = {}
        for dev in dispositivos:
            # Regla NetBox 4.6: Acceso mediante el atributo unificado .role
            funcion_name = dev.role.name if dev.role else "Sin Función / Rol Asignado"
            
            if funcion_name not in grupos_por_funcion:
                grupos_por_funcion[funcion_name] = []
            grupos_por_funcion[funcion_name].append(dev)

        # --- RENDERIZADO DEL INFORME EN PANTALLA ---
        for funcion, lista_devs in grupos_por_funcion.items():
            # Título del bloque de función
            self.log_info(f"==================================================")
            self.log_info(f"🛠️ FUNCIÓN: {funcion.upper()} ({len(lista_devs)} dispositivos)")
            self.log_info(f"==================================================")
            
            for dev in lista_devs:
                # 1. Datos básicos obligatorios
                nombre = dev.name if dev.name else "S/N (Sin Nombre)"
                serial = dev.serial if dev.serial else "No registrado"
                ubicacion = dev.location.name if dev.location else "[Sin Ubicación]"
                
                # 2. Extracción limpia de la IP Primaria (si tiene una asignada)
                ip_direccion = "Sin IP"
                if dev.primary_ip:
                    # Dividimos el CIDR (ej: 192.168.1.5/24) para mostrar solo la IP limpia
                    ip_direccion = str(dev.primary_ip.address).split('/')[0]

                # 3. Extracción de campos personalizados solicitados (DDI y Extension)
                ddi = dev.custom_field_data.get('ddi') or "N/A"
                extension = dev.custom_field_data.get('extension') or "N/A"

                # Construcción de la línea de output formateada
                mensaje_linea = (
                    f"💻 {nombre} | "
                    f"🔢 S/N: {serial} | "
                    f"🌐 IP: {ip_direccion} | "
                    f"📍 Ubic: {ubicacion} | "
                    f"🆔 DDI: {ddi} | "
                    f"📞 Ext: {extension}"
                )
                
                # Se pinta con el check verde de éxito para máxima legibilidad
                self.log_success(mensaje_linea)
