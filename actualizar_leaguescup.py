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

def buscar_stream_evento(nombre_partido, lista_streams):
    EXCLUSIONES = [
        "latin america", "directv sports", "sky sports", "espn", 
        "fox sports", "bein sports", "movistar", "pack futbol"
    ]
    
    equipos = [
        re.sub(r'[^a-zA-Z0-9]', '', eq.lower()) 
        for eq in re.split(r'\bvs\b|\bv\b|\b-\b', nombre_partido, flags=re.IGNORECASE) 
        if eq.strip()
    ]
    
    candidatos_evento = []
    candidatos_opcion = []

    for stream in lista_streams:
        nombre_stream = stream.get("name", "").lower()
        stream_id = stream.get("stream_id")
        
        if not stream_id:
            continue

        if any(excl in nombre_stream for excl in EXCLUSIONES) and "vs" not in nombre_stream:
            continue

        coincide_equipo = any(eq in nombre_stream for eq in equipos if len(eq) > 3)
        
        if coincide_equipo:
            if "leagues cup" in nombre_stream or "vs" in nombre_stream or "op" in nombre_stream:
                candidatos_evento.append(stream_id)
            else:
                candidatos_opcion.append(stream_id)

    target_id = None
    if candidatos_evento:
        target_id = candidatos_evento[0]
    elif candidatos_opcion:
        target_id = candidatos_opcion[0]

    if target_id:
        return f"{SERVER_URL}/live/{USERNAME}/{PASSWORD}/{target_id}.ts"
    
    return None

# ==========================================
# GENERACIÓN DE ARCHIVOS
# ==========================================
def generar_archivos():
    now = datetime.datetime.now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Iniciando generación de Guía XMLTV y M3U...")

    streams = obtener_streams_xtream()

    canales = [
        {"id": "LeaguesCup1", "name": "Leagues Cup 1", "busqueda": "America vs Portland Timbers"},
        {"id": "LeaguesCup2", "name": "Leagues Cup 2", "busqueda": "San Diego vs Tijuana"},
        {"id": "LeaguesCup3", "name": "Leagues Cup 3", "busqueda": "Cruz Azul vs NYCFC"},
        {"id": "LeaguesCup4", "name": "Leagues Cup 4", "busqueda": "Necaxa vs Atlanta"}
    ]

    # Crear XMLTV
    tv = ET.Element("tv", {"generator-info-name": "GeneradorLeaguesCup"})

    m3u_content = "#EXTM3U\n"

    for idx, ch in enumerate(canales, 1):
        # Nodo de canal en XML
        channel_elem = ET.SubElement(tv, "channel", {"id": ch["id"]})
        dn = ET.SubElement(channel_elem, "display-name")
        dn.text = ch["name"]
        icon = ET.SubElement(channel_elem, "icon", {"src": "https://brandlogos.net/wp-content/uploads/2025/02/leagues_cup-logo_brandlogos.net_gxi1m.png"})

        # Buscar URL real del stream
        url_stream = buscar_stream_evento(ch["busqueda"], streams)
        if not url_stream:
            url_stream = f"{SERVER_URL}/live/{USERNAME}/{PASSWORD}/1053641.ts"

        # M3U Entry
        m3u_content += f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-name="{ch["name"]}" tvg-logo="https://brandlogos.net/wp-content/uploads/2025/02/leagues_cup-logo_brandlogos.net_gxi1m.png" group-title="Leagues Cup",{ch["name"]}\n'
        m3u_content += f'{url_stream}\n'

        # Programme ficticio para mantener la guía viva con offset -0600
        start_time = now.strftime("%Y%m%d") + "000000 -0600"
        end_time = (now + datetime.timedelta(days=1)).strftime("%Y%m%d") + "235959 -0600"
        prog = ET.SubElement(tv, "programme", {
            "start": start_time,
            "stop": end_time,
            "channel": ch["id"]
        })
        title = ET.SubElement(prog, "title", {"lang": "es"})
        title.text = f"Transmisión en Vivo: {ch['busqueda']}"

    # Guardar XML
    xml_str = minidom.parseString(ET.tostring(tv, encoding="utf-8")).toprettyxml(indent="  ")
    with open(PATH_XMLTV, "w", encoding="utf-8") as f:
        f.write(xml_str)

    # Guardar M3U
    with open(PATH_M3U, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"Guía XMLTV ({PATH_XMLTV}) actualizada.")
    print(f"Playlist M3U ({PATH_M3U}) actualizada.")

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
