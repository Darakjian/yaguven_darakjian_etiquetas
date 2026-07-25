from odoo import models

# Prioridad de familia de piedra: la primera que tenga "Carat Weight" cargado
# es la que se usa para armar la etiqueta.
STONE_FAMILIES = [
    "Center Diamond",
    "Diamond",
    "Gem",
    "Accent Stone",
    "Sapphire",
    "Ruby",
    "Emerald",
]

LABEL_WIDTH_DOTS = 406   # 2in @ 203dpi (confirmado contra la impresora real)
LABEL_HEIGHT_DOTS = 113  # ~0.56in @ 203dpi (confirmado contra la impresora real)


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_attribute_map(self):
        """Atributos de la pieza, combinando template y variante.

        Los datos gemologicos (carat, clarity, color, origin, shape) estan
        configurados como `no_variant`: Odoo los deja en la linea del template
        y NUNCA los cuelga de `product_template_attribute_value_ids`. Leer solo
        la variante devolvia la etiqueta sin la ficha de la piedra.

        Del template se toman unicamente las lineas de UN solo valor: si tiene
        varios (ej. Material = White/Rose/Yellow Gold) es un atributo que genera
        variantes, y el valor que corresponde a esta pieza lo aporta la variante.
        """
        self.ensure_one()
        vals = {}
        for line in self.product_tmpl_id.attribute_line_ids:
            if len(line.value_ids) == 1:
                vals[line.attribute_id.name] = line.value_ids.name
        # La variante manda: pisa al template donde tenga valor propio.
        for ptav in self.product_template_attribute_value_ids:
            vals[ptav.attribute_id.name] = ptav.name
        return vals

    def _get_stone_specs(self, attr_map):
        for family in STONE_FAMILIES:
            carat = attr_map.get("%s Carat Weight" % family)
            if carat:
                return {
                    "carat": carat,
                    "clarity": attr_map.get("%s Clarity" % family, ""),
                    "color": attr_map.get("%s Color" % family, ""),
                    "quantity": attr_map.get("%s Quantity" % family, ""),
                }
        return {}

    def get_jewelry_label_zpl(self):
        self.ensure_one()
        attr_map = self._get_attribute_map()
        specs = self._get_stone_specs(attr_map)
        karatage = attr_map.get("Karatage", "")
        metal = attr_map.get("Material") or attr_map.get("Primary Color", "")
        origin = attr_map.get("Diamond Origin") or attr_map.get("Center Diamond Origin", "")

        name = (self.name or "")[:28]
        sku = self.default_code or ""
        price = "$ {:,.2f}".format(self.lst_price)

        left1 = specs.get("carat", "")
        left2 = specs.get("clarity", "")
        left3 = "{}   {}".format(specs.get("color", ""), specs.get("carat", "")).strip()
        left4 = "{}   {}".format(specs.get("quantity", ""), karatage).strip()
        left5 = "{} {}".format(origin, metal).strip()

        return (
            "^XA"
            "^PW{width}^LL{height}"
            # Interlineado 21 dots arrancando en y=4: la 5a fila termina en 106,
            # dentro de los 113 de alto. Con el paso anterior (22 desde y=8) la
            # ultima linea caia en 114 y salia cortada por el borde.
            "^FO10,4^A0N,18,18^FD{left1}^FS"
            "^FO160,4^A0N,18,18^FD{sku}^FS"
            "^FO10,25^A0N,18,18^FD{left2}^FS"
            "^FO160,25^A0N,16,16^FD{name}^FS"
            "^FO10,46^A0N,18,18^FD{left3}^FS"
            "^FO160,46^A0N,20,20^FD{price}^FS"
            "^FO10,67^A0N,18,18^FD{left4}^FS"
            "^FO10,88^A0N,18,18^FD{left5}^FS"
            "^XZ"
        ).format(
            width=LABEL_WIDTH_DOTS,
            height=LABEL_HEIGHT_DOTS,
            left1=left1,
            left2=left2,
            left3=left3,
            left4=left4,
            left5=left5,
            sku=sku,
            name=name,
            price=price,
        )
