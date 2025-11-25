# test_tarif_dialog.py

from tarif_dialog import handle_tariff_message
from typing import Dict, Any


def fake_get_products():
    # simulated products, same structure as real SAP getProducts()
    return [
        {"productId": "X1", "name": "Test-Tarif 1", "laufzeit": "12 Monate"},
        {"productId": "X2", "name": "Test-Tarif 2", "laufzeit": "24 Monate"},
    ]


def main():
    ctx: Dict[str, Any] = {}

    print("User: Ich möchte eine Tarifberatung")
    reply, ctx = handle_tariff_message("Ich möchte eine Tarifberatung", ctx, fake_get_products)
    print("Bot:", reply)

    print("\nUser: 3000")
    reply, ctx = handle_tariff_message("3000", ctx, fake_get_products)
    print("Bot:", reply)

    print("\nUser: 52062")
    reply, ctx = handle_tariff_message("52062", ctx, fake_get_products)
    print("Bot:", reply)


if __name__ == "__main__":
    main()
