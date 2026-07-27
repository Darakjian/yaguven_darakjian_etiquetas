{
    "name": "Darakjian - Etiquetas Zebra",
    "version": "19.0.1.2.0",
    "summary": "Impresión de etiquetas de joyería en impresoras Zebra desde el navegador",
    "category": "Inventory",
    "author": "Yaguven C.G.",
    "depends": ["product", "stock"],
    "data": [
        "views/product_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "yaguven_darakjian_etiquetas/static/src/js/print_label_button.js",
            "yaguven_darakjian_etiquetas/static/src/xml/print_label_button.xml",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
