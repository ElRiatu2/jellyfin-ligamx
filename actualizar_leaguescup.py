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

PATH_XMLTV = "/home/alam/jellyfin_ligamx/guia_leaguescup.xml"
DIR_REPO = "/home/alam/jellyfin_ligamx"

JELLYFIN_URL = "http://localhost:8096"
JELLYFIN_API_KEY = "3f91f99eff164770b01b000254cc7693"

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
                "dt_end": dt_end
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

def distribuir_en_los_4_canales_fijos(partidos):
    canales = {f"LeaguesCup{i}": [] for i in range(1, 5)}

    for partido in partidos:
        colocado = False
        for ch_id in ["LeaguesCup1", "LeaguesCup2", "LeaguesCup3", "LeaguesCup4"]:
            traslapa = False
            for p in canales[ch_id]:
                if not (partido["dt_end"] <= p["dt_start"] or partido["dt_start"] >= p["dt_end"]):
                    traslapa = True
                    break
            if not traslapa:
                canales[ch_id].append(dict(partido))
                colocado = True
                break
        
        if not colocado:
            canal_menos_cargado = min(canales, key=lambda k: len(canales[k]))
            canales[canal_menos_cargado].append(dict(partido))

    for ch_id in canales:
        canales[ch_id].sort(key=lambda x: x["dt_start"])
        for i in range(len(canales[ch_id]) - 1):
            actual = canales[ch_id][i]
            siguiente = canales[ch_id][i + 1]
            if actual["dt_end"] > siguiente["dt_start"]:
                actual["dt_end"] = siguiente["dt_start"]

    return canales

def generar_xmltv():
    now = datetime.datetime.now()
    streams = obtener_streams_xtream()
    partidos = extraer_partidos_del_dia(streams, now)
    canales_programacion = distribuir_en_los_4_canales_fijos(partidos)

    tv = ET.Element("tv", {"generator-info-name": "GeneradorLeaguesCup Fijo 4 Canales"})

    for i in range(1, 5):
        ch_id = f"LeaguesCup{i}"
        ch_name = f"Leagues Cup {i}"

        channel_elem = ET.SubElement(tv, "channel", {"id": ch_id})
        dn = ET.SubElement(channel_elem, "display-name")
        dn.text = ch_name
        ET.SubElement(channel_elem, "icon", {"src": "https://brandlogos.net/wp-content/uploads/2025/02/leagues_cup-logo_brandlogos.net_gxi1m.png"})

        partidos_canal = canales_programacion[ch_id]

        if partidos_canal:
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
        else:
            start_str = now.strftime("%Y%m%d000000 -0600")
            end_str = (now + datetime.timedelta(days=1)).strftime("%Y%m%d235959 -0600")
            prog = ET.SubElement(tv, "programme", {"start": start_str, "stop": end_str, "channel": ch_id})
            title = ET.SubElement(prog, "title", {"lang": "es"})
            title.text = "Sin evento programado"
            desc = ET.SubElement(prog, "desc", {"lang": "es"})
            desc.text = "No hay transmisión activa en este canal."

    tree = ET.ElementTree(tv)
    tree.write(PATH_XMLTV, encoding="utf-8", xml_declaration=True)
    print("XMLTV reescrito sin traslapes de horario.")

def ejecutar_git_y_notificar_jellyfin():
    os.chdir(DIR_REPO)
    try:
        subprocess.run(["git", "add", "guia_leaguescup.xml"], check=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        subprocess.run(["git", "commit", "-m", f"Fix XML overlap & sync EPG: {timestamp}"], check=False)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Git Push completado.")
    except Exception as e:
        print(f"Error en Git: {e}")

    headers = {
        "X-Emby-Token": JELLYFIN_API_KEY,
        "Authorization": f'MediaBrowser Token="{JELLYFIN_API_KEY}"'
    }
    
    try:
        tasks_res = requests.get(f"{JELLYFIN_URL}/ScheduledTasks", headers=headers, timeout=10)
        if tasks_res.status_code == 200:
            tasks = tasks_res.json()
            for task in tasks:
                if task.get("Key") == "RefreshGuide" or "Guide" in task.get("Name", ""):
                    task_id = task.get("Id")
                    requests.post(f"{JELLYFIN_URL}/ScheduledTasks/Running/{task_id}", headers=headers, timeout=10)
                    print(f"Tarea de actualización disparada en Jellyfin (ID: {task_id})")
                    break
        elif tasks_res.status_code == 401:
            print("Error 401: API Key rechazada. Por favor, genera una nueva API Key en Jellyfin (Panel de Control > Avanzado > Claves API) y actualiza la variable JELLYFIN_API_KEY.")
        else:
            print(f"Error al consultar ScheduledTasks: Status {tasks_res.status_code}")
    except Exception as e:
        print(f"Error al conectar con la API de Jellyfin: {e}")

if __name__ == "__main__":
    generar_xmltv()
    ejecutar_git_y_notificar_jellyfin()
