# tarif_dialog.py
"""
Dialog-Logik für die Tarifberatung.

Diese Datei kennt KEIN Telegram, nur:
- message: Eingabetext des Nutzers
- context_data: dict für den Zustand (z.B. telegram user_data["tarifdialog"])
- get_products_func: Funktion, die eine Produktliste aus SAP liefert

Funktion handle_tariff_message() kann:
- Einstieg in die Tarifberatung
- Verbrauch abfragen
- Postleitzahl abfragen
- dann getProducts() aufrufen
- 1–3 Tarife als Text zurückgeben
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List
import json
import logging

logger = logging.getLogger(__name__)


# -----------------------------
# Kontext-Objekt für den Dialog
# -----------------------------
@dataclass
class TariffContext:
    """
    Hält den Status der Tarifberatung für einen Nutzer.
    """
    step: str = "IDLE"  # mögliche Werte: IDLE, ASK_CONSUMPTION, ASK_POSTCODE, SHOW_PRODUCTS
    consumption: str | None = None
    postcode: str | None = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TariffContext":
        """Context aus einem dict (z.B. telegram user_data) laden."""
        return cls(
            step=data.get("step", "IDLE"),
            consumption=data.get("consumption"),
            postcode=data.get("postcode"),
            extra=data.get("extra", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Context zurück in dict wandeln (z.B. um ihn in user_data zu speichern)."""
        return {
            "step": self.step,
            "consumption": self.consumption,
            "postcode": self.postcode,
            "extra": self.extra,
        }


# -----------------------------
# Hilfsfunktionen
# -----------------------------
def default_start_message() -> str:
    return (
        "Gerne helfe ich dir bei der Tarifberatung! ✨\n"
        "Wie hoch ist dein jährlicher Stromverbrauch in kWh?"
    )


# -----------------------------
# Hauptfunktion
# -----------------------------
def handle_tariff_message(
    message: str,
    context_data: Dict[str, Any],
    get_products_func: Callable[[], List[Dict[str, Any]]],
) -> tuple[str, Dict[str, Any]]:
    """
    Zentrale Dialogfunktion.

    :param message: Eingabetext des Nutzers
    :param context_data: dict mit aktuellem Dialogzustand (z.B. telegram user_data["tarifdialog"])
    :param get_products_func: Funktion, die Produktliste aus SAP liefert (z.B. getProducts)
    :return: (reply_text, updated_context_data)
    """

    ctx = TariffContext.from_dict(context_data)
    msg = message.strip()

    # Einstieg: wir starten die Tarifberatung, wenn der Kontext im IDLE ist.
    # (Intent-Erkennung kann vorher passieren; hier vereinfachen wir.)
    if ctx.step == "IDLE":
        ctx.step = "ASK_CONSUMPTION"
        reply = default_start_message()
        return reply, ctx.to_dict()

    # Schritt 1: Verbrauch abfragen
    if ctx.step == "ASK_CONSUMPTION":
        ctx.consumption = msg
        ctx.step = "ASK_POSTCODE"
        reply = "Danke! Wie lautet deine Postleitzahl?"
        return reply, ctx.to_dict()

    # Schritt 2: Postleitzahl abfragen und dann Produkte holen
    if ctx.step == "ASK_POSTCODE":
        ctx.postcode = msg
        ctx.step = "SHOW_PRODUCTS"

        logger.info(
            "[TarifDialog] Starte getProducts() für Verbrauch=%s, PLZ=%s",
            ctx.consumption,
            ctx.postcode,
        )

        try:
            products = get_products_func()
        except Exception as e:
            # Wenn getProducts crasht → Fehler melden + Kontext zurücksetzen
            logger.exception("[TarifDialog] Fehler bei getProducts(): %r", e)
            reply = (
                "Beim Laden der verfügbaren Tarife ist ein Fehler aufgetreten. "
                "Bitte versuche es später noch einmal."
            )
            ctx.step = "IDLE"
            return reply, ctx.to_dict()

        # Logging für das Akzeptanzkriterium (echte Daten im Log sichtbar)
        try:
            logger.info(
                "[TarifDialog] Produkte aus API (gekürzt): %s",
                json.dumps(products, ensure_ascii=False)[:1000],
            )
        except Exception:
            logger.info("[TarifDialog] Produkte aus API (Rohformat): %r", products)

        if not products:
            reply = (
                "Ich konnte leider keine passenden Tarife finden. "
                "Bitte versuche es später erneut."
            )
            ctx.step = "IDLE"
            return reply, ctx.to_dict()

        top3 = products[:3]

        # Nochmals loggen, was wir dem Nutzer wirklich anzeigen
        logger.info(
            "[TarifDialog] Dem Nutzer angezeigte Produkte: %s",
            [
                {"productId": p.get("productId"), "name": p.get("name")}
                for p in top3
            ],
        )

        lines = ["Ich habe folgende Tarife für dich gefunden:\n"]
        for i, p in enumerate(top3, start=1):
            name = p.get("name") or "Tarif"
            pid = p.get("productId") or "unbekannt"
            laufzeit = p.get("laufzeit") or "-"
            lines.append(f"{i}. {name} (Produkt-ID: {pid}, Laufzeit: {laufzeit})")

        reply = "\n".join(lines)
        ctx.step = "IDLE"  # Dialog nach Anzeige der Produkte beenden/zurücksetzen
        return reply, ctx.to_dict()

    # Fallback – falls der Kontext in einem unbekannten Zustand ist
    logger.debug("[TarifDialog] Fallback – Kontext unbekannt, resette Dialog.")
    ctx = TariffContext(step="ASK_CONSUMPTION")
    reply = default_start_message()
    return reply, ctx.to_dict()


# -----------------------------
# Kleiner Self-Test (optional)
# -----------------------------
if __name__ == "__main__":
    """
    Wird nur ausgeführt, wenn du `python tarif_dialog.py` direkt startest.
    Nutzt eine Fake-getProducts-Funktion, um den Flow zu testen.
    """

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    def fake_get_products():
        # Simuliert getProducts() für lokalen Test
        return [
            {
                "productId": "P001",
                "name": "INTENSIVE ENERGY 12",
                "laufzeit": "12 Monate",
            },
            {
                "productId": "P002",
                "name": "INTENSIVE ENERGY 24",
                "laufzeit": "24 Monate",
            },
            {
                "productId": "P003",
                "name": "Day & Night 12",
                "laufzeit": "12 Monate",
            },
        ]

    ctx_dict: Dict[str, Any] = {}

    print("=== Testlauf TarifDialog (ohne Telegram) ===")

    # Einstieg
    reply, ctx_dict = handle_tariff_message("Ich möchte eine Tarifberatung", ctx_dict, fake_get_products)
    print("Bot:", reply)

    # Verbrauch
    reply, ctx_dict = handle_tariff_message("3500", ctx_dict, fake_get_products)
    print("Bot:", reply)

    # Postleitzahl → hier wird fake_get_products() aufgerufen
    reply, ctx_dict = handle_tariff_message("52062", ctx_dict, fake_get_products)
    print("Bot:", reply)

    print("=== Ende Testlauf ===")
