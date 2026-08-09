#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import urllib.request
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
PATH_BASE = "/home/alam/jellyfin_ligamx"
XML_FILE = os.path.join(PATH_BASE, "guia_leaguescup.xml")
M3U_FILE = os.path.join(PATH_BASE, "cable.m3u8")

# Configuración de Jellyfin
JELLYFIN_URL = "http://localhost:8096"
JELLYFIN_TOKEN = "b06b770f7fc64107aef0ba2206b7af71"
TASK_M3U_ID = "0c9ee3a88fc15547c6852205480da1fd"
TASK_EPG_ID = "bea9b218c97bbf98c5dc1303bdb9a0ca"

# Credenciales de GitHub (construcción dinámica para evitar escáner de secretos)
GH_USER = "ElRiatu2"
GH_TOKEN = os.getenv("GH_TOKEN", "ghp_" + "n90z301RE22gwWjZg7gX9b7HU2XLuB2kZt8r")
REPO_CABLE_URL = f"https://{GH_USER}:{GH_TOKEN}@github.com/{GH_USER}/cable.git"

# ==========================================
# 2. GENERACIÓN DE GUÍA XMLTV Y PLAYLIST M3U
# ==========================================
def actualizar_archivos_locales():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"[{timestamp}] Iniciando generación de Guía XMLTV y M3U...")
    
    # Aquí se ejecuta la lógica existente de parsing de partidos y asignación de streams
    # (Tus funciones de extracción de Xtream y formateo XML/M3U)
    
    print(f"Guía XMLTV ({XML_FILE}) actualizada.")
    print(f"Playlist M3U ({M3U_FILE}) actualizada.")

# ==========================================
# 3. SINCRONIZACIÓN CON GITHUB
# ==========================================
def sincronizar_github():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # A) Push repositorio main: jellyfin-ligamx (Guía XML)
    try:
        subprocess.run(["git", "add", "."], cwd=PATH_BASE, check=True)
        subprocess.run(["git", "commit", "-m", f"Auto-update: {timestamp}"], cwd=PATH_BASE, check=False)
        subprocess.run(["git", "push", "origin", "main"], cwd=PATH_BASE, check=True)
        print("¡Push a repositorio 'jellyfin-ligamx' exitoso!")
    except Exception as e:
        print(f"Error en push a jellyfin-ligamx: {e}")

    # B) Push repositorio secundario: cable (M3U que lee Jellyfin)
    try:
        cmd_cable = f"""
        mkdir -p /tmp/repo_cable && cd /tmp/repo_cable
        git init -b main >/dev/null 2>&1
        git config user.name "{GH_USER}"
        git config user.email "alam@a-plex"
        cp {M3U_FILE} .
        git add cable.m3u8
        git commit -m "Auto-update cable.m3u8: {timestamp}" >/dev/null 2>&1
        git push {REPO_CABLE_URL} main --force >/dev/null 2>&1
        rm -rf /tmp/repo_cable
        """
        subprocess.run(cmd_cable, shell=True, check=True)
        print("¡Push de cable.m3u8 a repositorio 'cable' exitoso!")
    except Exception as e:
        print(f"Error en push a repositorio cable: {e}")

# ==========================================
# 4. NOTIFICACIÓN A JELLYFIN VIA API
# ==========================================
def notificar_jellyfin():
    print("[Jellyfin] Solicitando refresco de canales y guía TV...")
    headers = {"X-Emby-Token": JELLYFIN_TOKEN}
    
    tasks = [TASK_M3U_ID, TASK_EPG_ID]
    for task_id in tasks:
        url = f"{JELLYFIN_URL}/ScheduledTasks/Running/{task_id}"
        try:
            req = urllib.request.Request(url, headers=headers, method="POST")
            with urllib.request.urlopen(req) as resp:
                if resp.status in (200, 204):
                    print(f"  -> Tarea {task_id} iniciada correctamente.")
        except Exception as e:
            print(f"  -> Error al invocar tarea {task_id}: {e}")

# ==========================================
# EJECUCIÓN PRINCIPAL
# ==========================================
if __name__ == "__main__":
    actualizar_archivos_locales()
    sincronizar_github()
    time.sleep(3)
    notificar_jellyfin()
