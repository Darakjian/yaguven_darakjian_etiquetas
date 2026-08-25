{
    "name": "Darakjian - Zebra Tag Printing",
    "version": "19.0.5.2.0",
    "summary": "Print jewelry tags on Zebra printers straight from the browser",
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
