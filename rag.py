import os
import time
import json
import hashlib
import requests
from pathlib import Path


BASE_URL = "http://192.168.1.10:8080" ----> your owui url
TOKEN = "sk-xxxxxxxxxxxxxxx" -----> your api key in settings/account
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json"
}
CACHE_FILE = ".uploaded_files.json"
SUPPORTED_EXTS = {"pdf", "txt", "html", "csv"}

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def file_hash(file_path):
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def validate_knowledge_id(knowledge_id):
    url = f"{BASE_URL}/api/v1/knowledge/{knowledge_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        return True
    print(f"❌ Error al validar knowledge_id: {resp.status_code} - {resp.text}")
    return False

def create_knowledge(name, description=""):
    url = f"{BASE_URL}/api/v1/knowledge/create"
    headers = HEADERS | {"Content-Type": "application/json"}
    payload = {
        "name": name,
        "description": description,
        "data": {},
        "access_control": {}
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 200:
        return resp.json().get("id")
    print(f"❌ Error al crear colección: {resp.status_code} - {resp.text}")
    return None

def upload_file(file_path):
    url = f"{BASE_URL}/api/v1/files/"
    mime_type = "text/plain" if file_path.suffix.lower() == ".txt" else "application/octet-stream"
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, mime_type)}
        resp = requests.post(url, headers=HEADERS, files=files)
    if resp.status_code == 200:
        return resp.json().get("id")
    print(f"❌ {file_path.name} upload failed: {resp.status_code} {resp.text}")
    return None

def add_file_to_knowledge(knowledge_id, file_id):
    url = f"{BASE_URL}/api/v1/knowledge/{knowledge_id}/file/add"
    headers = HEADERS | {"Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"file_id": file_id})
    return resp.status_code == 200

def main():
    folder = Path(input("📁 Carpeta de documentos: ").strip())
    if not folder.is_dir():
        print("❌ Carpeta no válida.")
        return

    choice = input("🆕 ¿Crear nueva colección? (s/n): ").strip().lower()
    if choice == "s":
        name = input("📚 Nombre de la colección: ").strip()
        description = input("📝 Descripción (opcional): ").strip()
        knowledge_id = create_knowledge(name, description)
        if not knowledge_id:
            return
    else:
        knowledge_id = input("📚 ID de la colección existente: ").strip()
        if not validate_knowledge_id(knowledge_id):
            return

    print(f"\n📂 Buscando archivos en {folder}...")
    files = [p for p in folder.rglob("*") if p.suffix[1:].lower() in SUPPORTED_EXTS]
    total = len(files)
    print(f"📄 {total} archivos encontrados\n")

    uploaded = load_cache()

    if uploaded:
        decision = input("📌 Ya hay archivos subidos. ¿Continuar donde se quedó (c) o reiniciar desde cero (r)? [c/r]: ").strip().lower()
        if decision == "r":
            uploaded = {}
            os.remove(CACHE_FILE)
            print("🗑️ Cache limpiado. Subida reiniciada desde cero.\n")
        else:
            print("🔄 Continuando con archivos pendientes...\n")

    success, skipped, failed = 0, 0, 0

    try:
        for index, file_path in enumerate(files):
            progress = (index + 1) / total * 100
            h = file_hash(file_path)
            if h in uploaded:
                print(f"[{progress:6.2f}%] ⏩ {file_path.name} ya subido. Saltando.")
                skipped += 1
                continue

            print(f"[{progress:6.2f}%] ⬆️ Subiendo {file_path.name}...")
            file_id = None
            retry_count = 0
            while retry_count < 3:
                file_id = upload_file(file_path)
                if file_id:
                    break
                retry_count += 1
                print(f"🔁 Reintentando {file_path.name}... ({retry_count}/3)")
                time.sleep(2)

            if not file_id:
                print(f"❌ Fallo definitivo en {file_path.name}")
                failed += 1
                continue

            time.sleep(1)  # opcional
            if add_file_to_knowledge(knowledge_id, file_id):
                print(f"✅ {file_path.name} agregado.")
                uploaded[h] = file_path.name
                success += 1
                save_cache(uploaded)
            else:
                print(f"❌ Falló al agregar {file_path.name}")
                failed += 1

    except KeyboardInterrupt:
        print("\n🛑 Proceso interrumpido por el usuario. Guardando progreso...")

    print("\n📊 Resumen final:")
    print(f"✅ Subidos: {success}")
    print(f"⏩ Saltados: {skipped}")
    print(f"❌ Fallidos: {failed}")

if __name__ == "__main__":
    main()


