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
        description = "Genera un documento PDF corporativo con diseño tecnológico, agrupado estrictamente por Grupos de Sitios."

    # --- FILTROS NO RESTRICTIVOS ---
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

        # 2. Agrupación estricta por Grupo de Sitios
        grupos_por_site_group = {}
        for dev in dispositivos:
            grupo_nombre = dev.site.group.name if (dev.site and dev.site.group) else "Sin Grupo de Sitios Asignado"
            
            if grupo_nombre not in grupos_por_site_group:
                grupos_por_site_group[grupo_nombre] = []
            grupos_por_site_group[grupo_nombre].append(dev)

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
        COLOR_PRIMARIO = colors.HexColor('#1e40af') 
        COLOR_TEXTO_OSCURO = colors.HexColor('#0f172a') 
        COLOR_SUBTITULOS = colors.HexColor('#64748b') 
        COLOR_LINEAS = colors.HexColor('#cbd5e1')
        COLOR_CEBRA = colors.HexColor('#f8fafc') 

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
            fontSize=12, textColor=COLOR_TEXTO_OSCURO, fontName='Helvetica-Bold',
            spaceBefore=12, spaceAfter=6
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
        story.append(Paragraph("Enterprise Asset Intelligence Report • Clasificado por Grupos de Sitios", estilo_sub))
        story.append(Spacer(1, 5))

        for grupo, lista_devs in grupos_por_site_group.items():
            story.append(Paragraph(f"■ GRUPO DE SITIOS: {grupo.upper()}", estilo_seccion))

            datos_tabla = [[
                Paragraph("Nombre", estilo_cabecera_tabla),
                Paragraph("Nº Serie", estilo_cabecera_tabla),
                Paragraph("Dirección IP", estilo_cabecera_tabla),
                Paragraph("Ubicación", estilo_cabecera_tabla),
                Paragraph("DDI", estilo_cabecera_tabla),
                Paragraph("Ext.", estilo_cabecera_tabla)
            ]]

            for dev in lista_devs:
                ip = str(dev.primary_ip.address).split('/')[0] if dev.primary_ip else "—"
                ddi = dev.custom_field_data.get('ddi') or "—"
                ext = dev.custom_field_data.get('extension') or "—"
                ubicacion_txt = dev.location.name if dev.location else "—"
                
                fila = [
                    Paragraph(dev.name or "S/N", estilo_celda),
                    Paragraph(dev.serial or "—", estilo_celda),
                    Paragraph(ip, estilo_celda),
                    Paragraph(ubicacion_txt, estilo_celda),
                    Paragraph(str(ddi), estilo_celda),
                    Paragraph(str(ext), estilo_celda)
                ]
                datos_tabla.append(fila)

            tabla_profesional = Table(datos_tabla, colWidths=[115, 85, 80, 115, 80, 70])
            
            diseno_tabla = TableStyle([
                ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARIO),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [COLOR_CEBRA, colors.white]),
                ('GRID', (0,0), (-1,-1), 0.5, COLOR_LINEAS),
            ])
            tabla_profesional.setStyle(diseno_tabla)

            story.append(tabla_profesional)
            story.append(Spacer(1, 10))

        # Compilar e imprimir el PDF
        doc.build(story)

        # 6. Salida en formato link nativo de NetBox
        self.log_success("==========================================================")
        self.log_success("🚀 ¡PDF EMPRESARIAL POR GRUPO DE SITIOS GENERADO!")
        # El formato [Texto](Ruta) crea un botón/enlace directo cliqueable en NetBox
        self.log_success(f"### [📥 CLIC AQUÍ PARA DESCARGAR EL PDF](/media/informes/{nombre_archivo})")
        self.log_success("==========================================================")
