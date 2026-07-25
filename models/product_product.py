from odoo import models

from .logo_zpl import LOGO_ZPL, LOGO_W, LOGO_H

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

# Cascadas de fallback: la primera que tenga valor es la que se imprime. Los
# atributos son excluyentes por tipo de pieza (un anillo trae Ring Size, un
# collar trae Length), por eso ninguno solo alcanza.
MEASURE_ATTRS = ["Ring Size", "Length", "Drop Length", "Width", "Diameter",
                 "Shank Width (M)", "Bracelet/Strap Length", "Gram Weight"]
CLASP_ATTRS = ["Clasp", "Earring Back", "Case Back"]

# El metal va abreviado, como en la etiqueta que ya usa la tienda ("YG").
METAL_ABBR = {
    "White Gold": "WG", "Yellow Gold": "YG", "Rose Gold": "RG",
    "Pink Gold": "PG", "Two Tone": "2T", "Tri Color": "3T",
    "Platinum": "PLT", "Palladium": "PD", "Titanium": "TI",
    "Sterling Silver": "SS", "Silver": "SLV", "Stainless Steel": "STL",
}

LABEL_WIDTH_DOTS = 406   # 2in @ 203dpi (confirmado contra la impresora real)
LABEL_HEIGHT_DOTS = 114  # MEDIDO: getvar zpl.label_length + ~HS (0114)

# Columnas, replicando la etiqueta fisica que ya usa la tienda: la mitad
# izquierda son DOS sub-columnas (ficha de la piedra | medidas y metal) y la
# derecha lleva SKU, descripcion y precio. El SKU va mas a la derecha que el
# nombre para dejarle lugar al cierre, que antes se le encimaba.
COL_A_X, COL_B_X = 10, 120
COL_NAME_X, COL_SKU_X = 205, 245

# (alto, ancho) por bloque. En ^A0N,h,w el `w` es el ancho NOMINAL por caracter.
FONT_A = (17, 13)
FONT_B = (17, 13)
FONT_SKU = (17, 13)
FONT_NAME = (22, 11)  # la descripcion es lo que mas mira el vendedor
FONT_PRICE = (20, 17)  # achicado para hacerle lugar al logo

# La fuente A0 es escalable y PROPORCIONAL: cada caracter ocupa bastante menos
# que el ancho nominal (una "i" mucho menos que una "W"). Medido contra el
# render real de la etiqueta, el promedio ronda el 65% del nominal. Sin este
# factor el recorte era conservador de mas y cortaba texto que si entraba.
CHAR_W_RATIO = 0.65

# Alto MEDIDO en la impresora real: `! U1 getvar "zpl.label_length"` -> 114 dots
# (y el ~HS lo confirma en su primer campo: 030,0,0,0114,...).
#
# El bloque necesita MARGEN ARRIBA Y ABAJO: el papel tiene un pequeno desfase
# fisico respecto del origen que asume la impresora, asi que lo impreso muy
# cerca de y=0 cae sobre el gap y sale cortado. Historia de las dos fallas:
#   y=4..114 (paso 21, fuente 18) -> se cortaba la ULTIMA fila, abajo
#   y=3..111 (paso 22, fuente 20) -> se cortaba la PRIMERA fila, arriba
# Ahora: 10, 29, 48, 67, 86 + 17 de alto = termina en 103, con 10 dots de
# margen arriba y 11 abajo.
FIRST_ROW_Y = 10
ROW_STEP_Y = 19

# El wordmark va abajo a la derecha, con el mismo margen que el resto.
LOGO_X = LABEL_WIDTH_DOTS - LOGO_W - 8
LOGO_Y = LABEL_HEIGHT_DOTS - LOGO_H - 8


def _fit(text, x_from, x_to, char_w):
    """Recorta el texto a los caracteres que entran entre dos columnas."""
    if not text:
        return ""
    return text[: max(0, int((x_to - x_from) / (char_w * CHAR_W_RATIO)))]


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

    def _first_of(self, attr_map, candidates):
        """Primer atributo de la cascada que tenga valor cargado."""
        for name in candidates:
            if attr_map.get(name):
                return attr_map[name]
        return ""

    def get_jewelry_label_zpl(self):
        self.ensure_one()
        attr_map = self._get_attribute_map()
        specs = self._get_stone_specs(attr_map)
        karatage = attr_map.get("Karatage", "")
        metal = attr_map.get("Material") or attr_map.get("Primary Color", "")
        metal = METAL_ABBR.get(metal, metal)
        origin = attr_map.get("Diamond Origin") or attr_map.get("Center Diamond Origin", "")
        measure = self._first_of(attr_map, MEASURE_ATTRS)
        clasp = self._first_of(attr_map, CLASP_ATTRS)

        sku = _fit(self.default_code or "", COL_SKU_X, LABEL_WIDTH_DOTS, FONT_SKU[1])
        name = _fit(self.name or "", COL_NAME_X, LABEL_WIDTH_DOTS, FONT_NAME[1])
        price = "$ {:,.2f}".format(self.lst_price)

        # Columna A: ficha de la piedra. Columna B: cierre, medida, metal.
        # Se recortan contra el inicio de la columna vecina para que nunca se
        # encimen (el cierre montandose sobre el SKU era el defecto de origen).
        col_a = [specs.get("carat", ""), specs.get("clarity", ""),
                 specs.get("color", ""), specs.get("quantity", ""), origin]
        col_b = [clasp, "", measure, karatage, metal]
        col_a = [_fit(v, COL_A_X, COL_B_X, FONT_A[1]) for v in col_a]
        col_b = [_fit(v, COL_B_X, COL_SKU_X - 4 if i == 0 else COL_NAME_X - 4, FONT_B[1])
                 for i, v in enumerate(col_b)]

        rows = "".join(
            "^FO{ax},{y}^A0N,{ah},{aw}^FD{a}^FS^FO{bx},{y}^A0N,{bh},{bw}^FD{b}^FS".format(
                ax=COL_A_X, bx=COL_B_X, y=FIRST_ROW_Y + ROW_STEP_Y * i,
                ah=FONT_A[0], aw=FONT_A[1], bh=FONT_B[0], bw=FONT_B[1],
                a=col_a[i], b=col_b[i])
            for i in range(5)
        )

        return (
            "^XA"
            "^PW{width}^LL{height}"
            # La columna derecha no comparte el paso de las filas de la
            # izquierda: son tres bloques de altura distinta (SKU, descripcion
            # y precio destacado), espaciados para que el precio quede alineado
            # con la fila de la medida, como en la etiqueta fisica.
            "{rows}"
            "^FO{sku_x},{sku_y}^A0N,{skuh},{skuw}^FD{sku}^FS"
            "^FO{name_x},{name_y}^A0N,{nh},{nw}^FD{name}^FS"
            "^FO{name_x},{price_y}^A0N,{ph},{pw}^FD{price}^FS"
            "^FO{logo_x},{logo_y}{logo}^FS"
            "^XZ"
        ).format(
            width=LABEL_WIDTH_DOTS,
            height=LABEL_HEIGHT_DOTS,
            rows=rows,
            sku_x=COL_SKU_X,
            name_x=COL_NAME_X,
            sku_y=FIRST_ROW_Y,
            name_y=FIRST_ROW_Y + 20,
            price_y=FIRST_ROW_Y + 47,
            skuh=FONT_SKU[0], skuw=FONT_SKU[1],
            nh=FONT_NAME[0], nw=FONT_NAME[1],
            ph=FONT_PRICE[0], pw=FONT_PRICE[1],
            sku=sku,
            name=name,
            price=price,
            logo_x=LOGO_X, logo_y=LOGO_Y, logo=LOGO_ZPL,
        )
