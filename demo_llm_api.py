import os
import requests
import json
import base64
from typing import Optional, Dict, Any
from dotenv import load_dotenv
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

CLIENT_ID = os.getenv("SAP_CLIENT_ID")
CLIENT_SECRET = os.getenv("SAP_CLIENT_SECRET")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

OPENROUTER_MODELS = [
    "tngtech/deepseek-r1t2-chimera:free",
]

PRODUCTS: Dict[str, Dict[str, Any]] = {}

# ============================================
# LLM (OpenRouter)
# ============================================

def call_llm(user_message: str) -> Dict[str, Any]:
    """
    Rufen Sie LLM über OpenRouter auf.
    Der LLM soll IMMER ein JSON mit:
      action, productId, consumptionR1, consumptionR2
    zurückgeben.
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "⚠️ OPENROUTER_API_KEY ist nicht gesetzt. "
            "Bitte Umgebungsvariable OPENROUTER_API_KEY konfigurieren."
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = """
Du bist ein Assistent für einen Stromtarif-Chatbot.
Du analysierst Benutzeranfragen und gibst IMMER eine JSON-Antwort zurück, ohne zusätzlichen Text.

Erlaubte Aktion:
- "simulate_price": Preissimulation für ein bestimmtes Produkt.

Verfügbare Produkte:
- INT12_DEMO_PROD: 12 Monate, nur ET (ein Verbrauch)
- INT24_DEMO_PROD: 24 Monate, nur ET
- INT_DNN_DEMO_PROD: 12 Monate, Day & Night (ET + NT)
- INT_DNN24_DEMO_PROD: 24 Monate, Day & Night (ET + NT)

Ausgabeformat (immer exakt dieses Schema):
{
  "action": "simulate_price",
  "productId": "...",
  "consumptionR1": <Zahl>,
  "consumptionR2": <Zahl>
}

Regeln:
- Wenn der Benutzer kein Produkt nennt, verwende "INT12_DEMO_PROD".
- Wenn der Benutzer nur einen Verbrauch nennt, setze consumptionR2 = 0.
- Wenn der Benutzer Day & Night erwähnt, verwende eines der DNN-Produkte und versuche ET/NT zu bestimmen.
- Gib NIEMALS etwas anderes als reines JSON zurück.
"""

    model = OPENROUTER_MODELS[0]

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }

    print(f"📡 [LLM] Sende Anfrage an OpenRouter mit Model '{model}' ...")
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload)

    if resp.status_code == 429:
        print(f"⚠️ [LLM] Model '{model}' ist rate-limited (429).")
        print("Body:", resp.text)
        raise SystemExit()

    if resp.status_code != 200:
        print("❌ [LLM] OpenRouter Fehler:", resp.status_code)
        print("Body:", resp.text)
        raise SystemExit()

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        print("❌ [LLM] Konnte Antwort nicht als JSON parsen.")
        print("Roh-Text:\n", text)
        raise

    return result

# ============================================
# SAP AUTH & PREISSIMULATION
# ============================================

def get_oauth_token() -> str:
    """Ein OAuth-Token wie mit Postman abrufen."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError(
            "⚠️ SAP_CLIENT_ID / SAP_CLIENT_SECRET sind nicht gesetzt. "
            "Bitte Umgebungsvariablen SAP_CLIENT_ID und SAP_CLIENT_SECRET konfigurieren."
        )

    token_url = "https://intense-ag-development.authentication.eu10.hana.ondemand.com/oauth/token"

    basic_auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {basic_auth}",
    }
    data = {"grant_type": "client_credentials"}

    print("🔐 [SAP] Hole OAuth Token ...")
    resp = requests.post(token_url, headers=headers, data=data)

    if resp.status_code != 200:
        print("❌ [SAP] Fehler beim Token holen:", resp.status_code)
        print("Body:", resp.text)
        resp.raise_for_status()

    token = resp.json()["access_token"]
    print("✅ [SAP] Token OK")
    return token

def simulate_price(
    token: str,
    product_id: str,
    r1: float,
    r2: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Preissimulations-API über CPI aufrufen.

    Im Postman-Beispiel wird ein GET mit JSON-Body verwendet.
    Wir machen hier das Gleiche, obwohl GET+Body eher unüblich ist.
    """
    url = (
        "https://intense-ag-development.it-cpi018-rt.cfapps.eu10-003.hana.ondemand.com"
        "/http/v1/s4/upil/product/simulation"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "ConsumptionR1": str(r1),
        "ProductID": product_id,
        "ConsumptionR2": "" if r2 is None else str(r2),
    }

    print(f"📡 [SAP] Sende Preissimulation (GET) für {product_id} (R1={r1}, R2={r2}) ...")
    resp = requests.get(url, headers=headers, json=body)

    if resp.status_code != 200:
        print("❌ [SAP] Fehler bei Preissimulation:", resp.status_code)
        print("Body:", resp.text)
        resp.raise_for_status()

    return resp.json()


def print_price_result(product_id: str, result: Dict[str, Any]) -> None:
    produkt = PRODUCTS.get(product_id, {})
    name = produkt.get("bezeichnung") or produkt.get("name") or product_id

    print("\n================ PREISSIMULATION ================")
    print(f"Produkt-ID   : {product_id}")
    print(f"Produktname  : {name}")
    print("\nAntwort der SAP-API:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=================================================\n")


def load_products_from_sap(token: str) -> Dict[str, Dict[str, Any]]:
    """
    Produkt-Information API aufrufen und ein Dict zurückgeben:
    { produktId: {...Daten aus SAP...}, ... }
    """
    url = (
        "https://intense-ag-development.it-cpi018-rt.cfapps.eu10-003.hana.ondemand.com"
        "/http/v1/s4/upil/product/information"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print("📡 [SAP] Lade Produktliste ...")
    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        print("❌ [SAP] Fehler beim Laden der Produktliste:", resp.status_code)
        print("Body:", resp.text)
        resp.raise_for_status()

    data = resp.json()

    # Erwartete Struktur wie im Postman:
    # { "products": [ {...}, {...}, ... ] }
    products_list = data.get("products", [])

    products_dict: Dict[str, Dict[str, Any]] = {}

    for p in products_list:
        pid = p.get("produktId")
        if not pid:
            continue
        
        status = (p.get("status") or "").lower()
        if status and status != "aktiv":
            # nur aktive Produkte
            continue
        products_dict[pid] = p

    print(f"✅ [SAP] {len(products_dict)} Produkte für Chatbot geladen.")
    return products_dict

# ============================================
# MAIN FLOW (LLM + SAP)
# ============================================

def main() -> None:
    global PRODUCTS

    print("=== CBIS Demo: LLM + OpenRouter + SAP Preissimulation ===")
    user_input = input("Geben Sie den Wunsch auf:\n> ")

    # 1) LLM: Benutzerwunsch analysieren
    try:
        llm_result = call_llm(user_input)
        print("✅ [LLM] Geparstes JSON:", llm_result)
    except Exception as e:
        print("🚨 Fehler beim Aufruf von LLM / JSON-Parsing:", repr(e))
        return

    action = llm_result.get("action")
    if action != "simulate_price":
        print("❌ LLM-Aktion nicht unterstützt:", action)
        return

    product_id = llm_result.get("productId", "INT12_DEMO_PROD")
    r1 = float(llm_result.get("consumptionR1", 3000))
    r2 = float(llm_result.get("consumptionR2", 0))

    # 2) OAuth-Token holen
    try:
        token = get_oauth_token()
    except Exception as e:
        print("🚨 Fehler beim Abrufen des OAuth-Tokens:", repr(e))
        return

    # 3) Produktliste laden
    try:
        PRODUCTS = load_products_from_sap(token)
    except Exception as e:
        print("🚨 Fehler beim Laden der Produktinformation:", repr(e))
        return

    if product_id not in PRODUCTS:
        print(f"❗ ProduktId '{product_id}' nicht in Produktliste gefunden.")
        print("   → LLM hat evtl. eine falsche ID gewählt.")
        print("   Verfügbare Produkte:", ", ".join(PRODUCTS.keys()))
        return

    # 4) Produkttyp (ET / DT) aus SAP ableiten
    product_info = PRODUCTS.get(product_id, {})
    et_dt = product_info.get("etDt", "ET")

    if et_dt == "ET":
        r2_value: Optional[float] = None
    else:
        r2_value = r2

    # 5) Preissimulation aufrufen
    try:
        result = simulate_price(token, product_id, r1, r2_value)
    except Exception as e:
        print("🚨 Fehler beim Aufruf von Preissimulation:", repr(e))
        return

    # 6) Ergebnis ausgeben
    print_price_result(product_id, result)

if __name__ == "__main__":
    main()
