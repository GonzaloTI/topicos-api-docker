import json
import requests

# Cargar el archivo JSON con las rutas
with open("rutas_async.json", "r", encoding="utf-8") as f:
    routes = json.load(f)

for route in routes:
    url = route["url"]
    method = route["method"].upper()
    body = route.get("body", None)

    print(f"\n➡ Ejecutando {method} {url}")
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=body)
        elif method == "PUT":
            response = requests.put(url, json=body)
        elif method == "DELETE":
            response = requests.delete(url)
        else:
            print(f"❌ Método no soportado: {method}")
            continue

        print(f"✅ Status: {response.status_code}")
        try:
            print("📄 Respuesta:", response.json())
        except:
            print("📄 Respuesta:", response.text)

    except Exception as e:
        print(f"⚠ Error ejecutando {method} {url}: {e}")
