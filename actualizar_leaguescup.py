import requests
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
import datetime
import subprocess
import os
import re

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
SERVER_URL = "http://aioplus.es:80"
USERNAME = "ALAM5462"
PASSWORD = "jVf3Q5Bg"

PATH_XMLTV = "/home/alam/jellyfin_ligamx/guia_leaguescup.xml"
PATH_M3U = "/home/alam/jellyfin_ligamx/cable.m3u8"
DIR_REPO = "/home/alam/jellyfin_ligamx"

JELLYFIN_URL = "http://localhost:8096"
JELLYFIN_API_KEY = "9a7db1b27e224e70876ff2a7e7bcbf20"

# ==========================================
# OBTENER STREAMS DE XTREAM
# ==========================================
def obtener_streams_xtream():
    url = f"{SERVER_URL}/player_api.php?username={USERNAME}&password={PASSWORD}&action=get_live_streams"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error al obtener streams de Xtream: {e}")
    return []

def extraer_partidos_del_dia(streams):
    """
    Filtra ÚNICAMENTE los eventos de Leagues Cup.
    Descarte estricto de otros deportes y torneos.
    """
    EXCLUSIONES = [
        "latin america", "directv sports", "sky sports", "espn", 
        "fox sports", "bein sports", "movistar", "pack futbol",
        "champions league", "rugby", "tennis", "formula 1", "f1", 
        "mlb", "nba", "liga betplay", "copa libertadores"
    ]
    
    eventos_encontrados = []

    for stream in streams:
        nombre = stream.get("name", "")
        nombre_lower = nombre.lower()
        stream_id = stream.get("stream_id")

        if not stream_id:
            continue

        # Descartar torneos/deportes no deseados
        if any(excl in nombre_lower for excl in EXCLUSIONES):
            continue

        # REQUISITO EXCLUSIVO: Debe ser explícitamente Leagues Cup
        if "leagues cup" in nombre_lower or "leagues" in nombre_lower:
            url_stream = f"{SERVER_URL}/live/{USERNAME}/{PASSWORD}/{stream_id}.ts"
            
            # Limpiar nombre comercial
            nombre_limpio = re.sub(r'^\d{2}:\d{2}\s+\d{2}/\d{2}\s*\|\s*', '', nombre)
            nombre_limpio = re.sub(r'\s*\|\s*(OP\d+|HD|FHD|UHD|4K|SD)\s*$', '', nombre_limpio, flags=re.IGNORECASE)

            eventos_encontrados.append({
                "titulo": nombre_limpio,
                "url": url_stream,
                "stream_id": stream_id
            })

    # Eliminar duplicados manteniendo el orden
    eventos_unicos = []
    vistos = set()
    for ev in eventos_encontrados:
        if ev["titulo"] not in vistos:
            vistos.add(ev["titulo"])
            eventos_unicos.append(ev)

    return eventos_unicos

# ==========================================
# GENERACIÓN DE ARCHIVOS
# ==========================================
def generar_archivos():
    now = datetime.datetime.now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Filtrando exclusivamente partidos de Leagues Cup...")

    streams = obtener_streams_xtream()
    partidos = extraer_partidos_del_dia(streams)

    tv = ET.Element("tv", {"generator-info-name": "GeneradorLeaguesCup"})
    m3u_content = "#EXTM3U\n"

    for i in range(1, 5):
        ch_id = f"LeaguesCup{i}"
        ch_name = f"Leagues Cup {i}"

        # Nodo canal XML
        channel_elem = ET.SubElement(tv, "channel", {"id": ch_id})
        dn = ET.SubElement(channel_elem, "display-name")
        dn.text = ch_name
        ET.SubElement(channel_elem, "icon", {"src": "https://brandlogos.net/wp-content/uploads/2025/02/leagues_cup-logo_brandlogos.net_gxi1m.png"})

        # Asignar evento de Leagues Cup o estado de espera si aún no hay transmisión activa
        if i - 1 < len(partidos):
            evento = partidos[i - 1]
            titulo_partido = evento["titulo"]
            url_stream = evento["url"]
        else:
            titulo_partido = "Sin partido de Leagues Cup programado en este momento"
            url_stream = f"{SERVER_URL}/live/{USERNAME}/{PASSWORD}/1053641.ts"

        # Entrada M3U
        m3u_content += f'#EXTINF:-1 tvg-id="{ch_id}" tvg-name="{ch_name}" tvg-logo="https://brandlogos.net/wp-content/uploads/2025/02/leagues_cup-logo_brandlogos.net_gxi1m.png" group-title="Leagues Cup",{ch_name}\n'
        m3u_content += f'{url_stream}\n'

        # Programa XMLTV dinámico
        start_time = now.strftime("%Y%m%d") + "000000 -0600"
        end_time = (now + datetime.timedelta(days=1)).strftime("%Y%m%d") + "235959 -0600"
        prog = ET.SubElement(tv, "programme", {
            "start": start_time,
            "stop": end_time,
            "channel": ch_id
        })
        title = ET.SubElement(prog, "title", {"lang": "es"})
        title.text = f"Transmisión en Vivo: {titulo_partido}"

    # Guardar XMLTV
    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    with open(PATH_XMLTV, "w", encoding="utf-8") as f:
        f.write(xml_str)

    # Guardar M3U
    with open(PATH_M3U, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"Guía XMLTV ({PATH_XMLTV}) actualizada con filtro estricto.")
    print(f"Playlist M3U ({PATH_M3U}) actualizada con filtro estricto.")

# ==========================================
# GIT & JELLYFIN
# ==========================================
def ejecutar_git_y_notificar():
    os.chdir(DIR_REPO)
    try:
        subprocess.run(["git", "add", "."], check=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(["git", "commit", "-m", f"Auto-update: {timestamp}"], check=False)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("¡Push a repositorio 'jellyfin-ligamx' exitoso!")
    except Exception as e:
        print(f"Error en Git push: {e}")

    # Notificar a Jellyfin
    headers = {"X-Emby-Token": JELLYFIN_API_KEY}
    try:
        r1 = requests.post(f"{JELLYFIN_URL}/ScheduledTasks/Running/0c9ee3a88fc15547c6852205480da1fd", headers=headers)
        r2 = requests.post(f"{JELLYFIN_URL}/ScheduledTasks/Running/bea9b218c97bbf98c5dc1303bdb9a0ca", headers=headers)
        if r1.status_code in [200, 204] and r2.status_code in [200, 204]:
            print("[Jellyfin] Solicitando refresco de canales y guía TV enviado con éxito.")
    except Exception as e:
        print(f"Error al notificar a Jellyfin: {e}")

if __name__ == "__main__":
    generar_archivos()
    ejecutar_git_y_notificar()
