import requests
import json
import xml.etree.ElementTree as ET
import datetime
import subprocess
import os
import re

SERVER_URL = "http://aioplus.es:80"
USERNAME = "ALAM5462"
PASSWORD = "jVf3Q5Bg"

PATH_XMLTV_1 = "/home/alam/jellyfin_ligamx/guia_leaguescup.xml"
PATH_XMLTV_2 = "/home/alam/jellyfin_ligamx/guia_ligamx.xml"
PATH_M3U = "/home/alam/jellyfin_ligamx/cable.m3u8"
DIR_REPO = "/home/alam/jellyfin_ligamx"

JELLYFIN_URL = "http://localhost:8096"
JELLYFIN_API_KEY = "9a7db1b27e224e70876ff2a7e7bcbf20"

def obtener_streams_xtream():
    url = f"{SERVER_URL}/player_api.php?username={USERNAME}&password={PASSWORD}&action=get_live_streams"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error al obtener streams: {e}")
    return []

def formatear_partido(nombre_raw):
    match_hora = re.search(r'(\d{2}:\d{2})', nombre_raw)
    hora_str = match_hora.group(1) if match_hora else None

    limpio = re.sub(r'^\d{2}:\d{2}\s+\d{2}/\d{2}\s*\|\s*', '', nombre_raw)
    limpio = re.sub(r'\s*\|\s*(leagues cup|op\d+|hd|fhd|uhd|4k|sd).*$', '', limpio, flags=re.IGNORECASE).strip()

    match = re.split(r'\s+(?:vs\.?|v\.?|-)\s+', limpio, flags=re.IGNORECASE)

    if len(match) == 2:
        local = match[0].strip()
        visita = match[1].strip()
        titulo = f"{local} vs {visita}: En Vivo"
        desc = f"Transmisión en vivo del partido entre {local} y {visita} por la Leagues Cup."
    else:
        titulo = f"{limpio}: En Vivo"
        desc = "Cobertura en vivo del evento de Leagues Cup."

    return titulo, desc, hora_str

def extraer_partidos_del_dia(streams, now):
    EXCLUSIONES = [
        "latin america", "directv sports", "sky sports", "espn", 
        "fox sports", "bein sports", "movistar", "pack futbol",
        "champions league", "rugby", "tennis", "formula 1", "f1", 
        "mlb", "nba", "liga betplay", "copa libertadores"
    ]
    
    eventos = []

    for stream in streams:
        nombre = stream.get("name", "")
        nombre_lower = nombre.lower()
        stream_id = stream.get("stream_id")

        if not stream_id or any(excl in nombre_lower for excl in EXCLUSIONES):
            continue

        if "leagues cup" in nombre_lower or "leagues" in nombre_lower:
            url_stream = f"{SERVER_URL}/live/{USERNAME}/{PASSWORD}/{stream_id}.ts"
            titulo, desc, hora_str = formatear_partido(nombre)

            if hora_str:
                try:
                    h, m = map(int, hora_str.split(":"))
                    dt_start = now.replace(hour=h, minute=m, second=0, microsecond=0)
                except Exception:
                    dt_start = now.replace(hour=18, minute=0, second=0, microsecond=0)
            else:
                dt_start = now.replace(hour=18, minute=0, second=0, microsecond=0)

            dt_end = dt_start + datetime.timedelta(hours=2, minutes=30)

            eventos.append({
                "titulo": titulo,
                "desc": desc,
                "dt_start": dt_start,
                "dt_end": dt_end,
                "url": url_stream
            })

    eventos.sort(key=lambda x: x["dt_start"])
    
    unicos = []
    vistos = set()
    for ev in eventos:
        key = f"{ev['titulo']}_{ev['dt_start'].strftime('%H:%M')}"
        if key not in vistos:
            vistos.add(key)
            unicos.append(ev)

    return unicos

def distribuir_en_canales(partidos):
    canales = {f"LeaguesCup{i}": [] for i in range(1, 5)}

    for partido in partidos:
        asignado = False
        for ch_id in ["LeaguesCup1", "LeaguesCup2", "LeaguesCup3", "LeaguesCup4"]:
            programas_canal = canales[ch_id]
            traslapa = False
            for p in programas_canal:
                if not (partido["dt_end"] <= p["dt_start"] or partido["dt_start"] >= p["dt_end"]):
                    traslapa = True
                    break
            
            if not traslapa:
                canales[ch_id].append(partido)
                asignado = True
                break

        if not asignado:
            canal_menos_cargado = min(canales, key=lambda k: len(canales[k]))
            canales[canal_menos_cargado].append(partido)

    return canales

def generar_archivos():
    now = datetime.datetime.now()
    streams = obtener_streams_xtream()
    partidos = extraer_partidos_del_dia(streams, now)
    canales_programacion = distribuir_en_canales(partidos)

    tv = ET.Element("tv", {"generator-info-name": "GeneradorLeaguesCup"})
    m3u_content = "#EXTM3U\n"

    # CANALES
    for i in range(1, 5):
        ch_id = f"LeaguesCup{i}"
        ch_name = f"Leagues Cup {i}"

        channel_elem = ET.SubElement(tv, "channel", {"id": ch_id})
        dn = ET.SubElement(channel_elem, "display-name")
        dn.text = ch_name
        ET.SubElement(channel_elem, "icon", {"src": "https://brandlogos.net/wp-content/uploads/2025/02/leagues_cup-logo_brandlogos.net_gxi1m.png"})

    # PROGRAMAS
    for i in range(1, 5):
        ch_id = f"LeaguesCup{i}"
        ch_name = f"Leagues Cup {i}"
        partidos_canal = canales_programacion[ch_id]
        url_activa_m3u = ""

        if partidos_canal:
            partidos_canal.sort(key=lambda x: x["dt_start"])

            for p in partidos_canal:
                start_str = p["dt_start"].strftime("%Y%m%d%H%M%S -0600")
                end_str = p["dt_end"].strftime("%Y%m%d%H%M%S -0600")

                prog = ET.SubElement(tv, "programme", {
                    "start": start_str,
                    "stop": end_str,
                    "channel": ch_id
                })
                title = ET.SubElement(prog, "title", {"lang": "es"})
                title.text = p["titulo"]
                desc = ET.SubElement(prog, "desc", {"lang": "es"})
                desc.text = p["desc"]

                if p["dt_start"] <= now <= p["dt_end"]:
                    url_activa_m3u = p["url"]

            if not url_activa_m3u:
                proximos = [p for p in partidos_canal if p["dt_start"] > now]
                if proximos:
                    url_activa_m3u = proximos[0]["url"]
                else:
                    url_activa_m3u = partidos_canal[-1]["url"]
        else:
            start_str = now.strftime("%Y%m%d000000 -0600")
            end_str = (now + datetime.timedelta(days=1)).strftime("%Y%m%d235959 -0600")
            prog = ET.SubElement(tv, "programme", {"start": start_str, "stop": end_str, "channel": ch_id})
            title = ET.SubElement(prog, "title", {"lang": "es"})
            title.text = "Sin partido programado"
            desc = ET.SubElement(prog, "desc", {"lang": "es"})
            desc.text = "No hay partidos asignados a este canal en este momento."

        m3u_content += f'#EXTINF:-1 tvg-id="{ch_id}" tvg-name="{ch_name}" tvg-logo="https://brandlogos.net/wp-content/uploads/2025/02/leagues_cup-logo_brandlogos.net_gxi1m.png" group-title="Leagues Cup",{ch_name}\n'
        m3u_content += f'{url_activa_m3u}\n'

    tree = ET.ElementTree(tv)
    tree.write(PATH_XMLTV_1, encoding="utf-8", xml_declaration=True)
    tree.write(PATH_XMLTV_2, encoding="utf-8", xml_declaration=True)

    with open(PATH_M3U, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print("XMLTV (ambos nombres) y M3U reescritos correctamente.")

def ejecutar_git_y_notificar():
    os.chdir(DIR_REPO)
    try:
        subprocess.run(["git", "add", "."], check=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(["git", "commit", "-m", f"Fix 404 and XML export: {timestamp}"], check=False)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Push a repositorio exitoso!")
    except Exception as e:
        print(f"Error en Git push: {e}")

    headers = {"X-Emby-Token": JELLYFIN_API_KEY}
    try:
        r1 = requests.post(f"{JELLYFIN_URL}/ScheduledTasks/Running/0c9ee3a88fc15547c6852205480da1fd", headers=headers)
        r2 = requests.post(f"{JELLYFIN_URL}/ScheduledTasks/Running/bea9b218c97bbf98c5dc1303bdb9a0ca", headers=headers)
        if r1.status_code in [200, 204] and r2.status_code in [200, 204]:
            print("[Jellyfin] Tareas activadas.")
    except Exception as e:
        print(f"Error en API Jellyfin: {e}")

if __name__ == "__main__":
    generar_archivos()
    ejecutar_git_y_notificar()
