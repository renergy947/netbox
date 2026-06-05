import os
from django.conf import settings
from extras.scripts import Script, ObjectVar
from dcim.models import Device, Region, SiteGroup, Site, Location

# Componentes de maquetación profesional PDF (ReportLab)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class InformeGlobalPDF(Script):
    class Meta:
        name = "Informe de Activos a PDF"
        description = "Genera un documento PDF corporativo agrupado por Grupos de Sitios y subagrupado por Funciones del Dispositivo (Roles)."

    # --- FILTROS NO RESTRICTIVOS (Todos opcionales) ---
    region = ObjectVar(model=Region, required=False, label="Región")
    site_group = ObjectVar(model=SiteGroup, required=False, label="Grupo de Sitios")
    site = ObjectVar(model=Site, required=False, label="Sitio / Sede", query_params={'region_id': '$region', 'group_id': '$site_group'})
    location = ObjectVar(model=Location, required=False, label="Ubicación específica", query_params={'site_id': '$site'})

    def run(self, data, commit):
        # 1. Recuperación y filtrado dinámico de datos de la BD
        dispositivos = Device.objects.all()

        if data['region']: dispositivos = dispositivos.filter(site__region=data['region'])
        if data['site_group']: dispositivos = dispositivos.filter(site__group=data['site_group'])
        if data['site']: dispositivos = dispositivos.filter(site=data['site'])
        if data['location']: dispositivos = dispositivos.filter(location=data['location'])

        if not dispositivos.exists():
            self.log_warning("No se encontraron activos para los criterios seleccionados.")
            return

        # 2. --- DOBLE AGRUPACIÓN JERÁRQUICA (Grupo de Sitio -> Función del Dispositivo) ---
        estructura_informe = {}
        for dev in dispositivos:
            # Jerarquía 1: Grupo de Sitios
            grupo_nombre = dev.site.group.name if (dev.site and dev.site.group) else "Sin Grupo de Sitios Asignado"
            
            # Jerarquía 2: Función del Dispositivo (Device Role)
            funcion_nombre = dev.role.name if dev.role else "Sin Función Asignada"
            
            # Inicialización del árbol de datos
            if grupo_nombre not in estructura_informe:
                estructura_informe[grupo_nombre] = {}
            if funcion_nombre not in estructura_informe[grupo_nombre]:
                estructura_informe[grupo_nombre][funcion_nombre] = []
                
            estructura_informe[grupo_nombre][funcion_nombre].append(dev)

        # 3. Preparación del archivo físico en el directorio 'media'
        directorio_informes = os.path.join(settings.MEDIA_ROOT, 'informes')
        os.makedirs(directorio_informes, exist_ok=True)
        nombre_archivo = 'informe_activos_por_grupo_sitios.pdf'
        ruta_completa_pdf = os.path.join(directorio_informes, nombre_archivo)

        # 4. Configuración del documento A4
        doc = SimpleDocTemplate(
            ruta_completa_pdf, 
            pagesize=A4, 
            rightMargin=25, 
            leftMargin=25, 
            topMargin=25, 
            bottomMargin=25
        )
        story = []
        styles = getSampleStyleSheet()

        # --- PALETA DE COLORES EMPRESARIAL ---
        COLOR_PRIMARIO = colors.HexColor('#1e40af')   # Azul Corporativo
        COLOR_TEXTO_OSCURO = colors.HexColor('#0f172a') # Pizarra
        COLOR_SUBTITULOS = colors.HexColor('#64748b')   # Gris frío
        COLOR_LINEAS = colors.HexColor('#cbd5e1')       # Bordes
        COLOR_CEBRA = colors.HexColor('#f8fafc')        # Filas alternas
        COLOR_SUBGRUPO = colors.HexColor('#475569')     # Gris intermedio para la función

        # --- ESTILOS TIPOGRÁFICOS ---
        estilo_titulo = ParagraphStyle(
            'DocTitle', parent=styles['Heading1'],
            fontSize=22, textColor=COLOR_PRIMARIO, fontName='Helvetica-Bold', spaceAfter=4
        )
        estilo_sub = ParagraphStyle(
            'DocSub', parent=styles['Normal'],
            fontSize=9, textColor=COLOR_SUBTITULOS, fontName='Helvetica', spaceAfter=18
        )
        estilo_seccion = ParagraphStyle(
            'SecTitle', parent=styles['Heading2'],
            fontSize=13, textColor=COLOR_TEXTO_OSCURO, fontName='Helvetica-Bold',
            spaceBefore=16, spaceAfter=4
        )
        estilo_subgrupo = ParagraphStyle(
            'SubGroupTitle', parent=styles['Heading3'],
            fontSize=9.5, textColor=COLOR_SUBGRUPO, fontName='Helvetica-Bold',
            spaceBefore=6, spaceAfter=4, leftIndent=8
        )
        estilo_cabecera_tabla = ParagraphStyle(
            'TableHeader', parent=styles['Normal'],
            fontSize=8.5, textColor=colors.white, fontName='Helvetica-Bold', leading=10
        )
        estilo_celda = ParagraphStyle(
            'TableCell', parent=styles['Normal'],
            fontSize=8, textColor=COLOR_TEXTO_OSCURO, fontName='Helvetica', leading=10
        )

        # 5. CONSTRUCCIÓN DEL CONTENIDO DEL DOCUMENTO
        story.append(Paragraph("INFORME MAESTRO DE INFRAESTRUCTURA", estilo_titulo))
        story.append(Paragraph("Enterprise Asset Intelligence Report • Estructura Jerárquica por Funciones", estilo_sub))
        story.append(Spacer(1, 5))

        # --- BUCLE DE RENDERIZADO JERÁRQUICO ---
        # Iterar Nivel 1: Grupos de Sitios
        for grupo, subgrupos_funciones in estructura_informe.items():
            story.append(Paragraph(f"■ GRUPO DE SITIOS: {grupo.upper()}", estilo_seccion))

            # Iterar Nivel 2: Funciones del Dispositivo dentro de ese grupo
            for funcion, lista_devs in subgrupos_funciones.items():
                story.append(Paragraph(f"↳ Función: {funcion}", estilo_subgrupo))

                # Estructura de cabecera de la tabla (Ancho total A4 útil = 545 puntos)
                datos_tabla = [[
                    Paragraph("Nombre", estilo_cabecera_tabla),
                    Paragraph("Nº Serie", estilo_cabecera_tabla),
                    Paragraph("Dirección IP", estilo_cabecera_tabla),
                    Paragraph("Ubicación", estilo_cabecera_tabla),
                    Paragraph("DDI", estilo_cabecera_tabla),
                    Paragraph("Ext.", estilo_cabecera_tabla)
                ]]

                # Inyección de dispositivos pertenecientes a esta función exacta
                for dev in lista_devs:
                    ip = str(dev.primary_ip.address).split('/')[0] if dev.primary_ip else "—"
                    ddi = dev.custom_field_data.get('ddi') or "—"
                    ext = dev.custom_field_data.get('extension') or "—"
                    ubicacion_txt = dev.location.name if dev.location else "—"
                    
                    # Estructura plana compatible con Python 3.14
                    fila = [
                        Paragraph(dev.name or "S/N", estilo_celda),
                        Paragraph(dev.serial or "—", estilo_celda),
                        Paragraph(ip, estilo_celda),
                        Paragraph(ubicacion_txt, estilo_celda),
                        Paragraph(str(ddi), estilo_celda),
                        Paragraph(str(ext), estilo_celda)
                    ]
                    datos_tabla.append(fila)

                # Aplicar diseño corporativo a la tabla
                tabla_profesional = Table(datos_tabla, colWidths=[115, 85, 80, 115, 80, 70])
                
                diseno_tabla = TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARIO),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [COLOR_CEBRA, colors.white]),
                    ('GRID', (0,0), (-1,-1), 0.5, COLOR_LINEAS),
                ])
                tabla_profesional.setStyle(diseno_tabla)

                story.append(tabla_profesional)
                story.append(Spacer(1, 10))

        # Compilar e imprimir el PDF final
        doc.build(story)

        # 6. Mensaje de éxito final usando Markdown puro relativo
        self.log_success("==========================================================")
        self.log_success("🚀 ¡PDF JERÁRQUICO POR FUNCIONES GENERADO CON ÉXITO!")
        self.log_success(f"### [📥 HAZ CLIC AQUÍ PARA DESCARGAR EL PDF](/media/informes/{nombre_archivo})")
        self.log_success("==========================================================")
