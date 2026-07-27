from odoo import models

from .logo_zpl import LOGO_ZPL

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
LABEL_HEIGHT_DOTS = 112  # MEDIDO: calibracion ~JC del 27/07 -> zpl.label_length
                         # bajo de 0114 a 0112. Los 114 anteriores venian de la
                         # impresora SIN calibrar: el papel real mide 112 dots.

X0 = 10                              # margen lateral, parejo de los dos lados
X1 = LABEL_WIDTH_DOTS - X0
USABLE_W = X1 - X0                   # 386 dots de ancho util

# --- LAYOUT EN BANDAS -------------------------------------------------------
# Tres bandas horizontales, cada una con UN significado:
#
#   DARAKJIAN  DBRC.00081204                        $ 5,050.00
#   DIAMOND BEZEL TENNIS BRACELET
#   2.05Ct x57 SI2 G-H Color Mined | 14k YG | 7.00" | Box
#
#   1. identidad y plata: wordmark + SKU centrado + PRECIO a la derecha (arriba
#      a la derecha es donde cae el ojo primero).
#   2. QUE ES la pieza: la descripcion sola, a lo ancho de la etiqueta.
#   3. la ficha en una sola linea corrida, agrupada por sentido con "|":
#      piedra | aleacion | medida.
#
# POR QUE se dejaron las dos columnas de la etiqueta heredada: eran valores SIN
# ROTULO y CON HUECOS -- si la pieza no tenia cierre, lo de abajo "subia" y el
# mismo renglon cambiaba de significado segun la fila. Con el renglon corrido,
# si un dato falta el texto simplemente se acorta: no deja hueco ni corre de
# lugar a los demas.
#
# Y hay un efecto colateral que justifica el cambio por si solo: usando los 386
# dots enteros en vez de los ~200 de una columna derecha, las descripciones
# entran COMPLETAS. Antes se cortaban a mitad de palabra ("...TENNIS BRACELE").
#
# El bloque va de y=20 a y=92 sobre 112 de alto: 20 dots de margen arriba y 20
# abajo, REPARTIDOS PAREJO. Ese aire es lo que evita que el registro del papel
# se coma la primera o la ultima fila.
#
# Historia de por que quedo asi (27/07): con 14 arriba / 20 abajo sobre un alto
# supuesto de 114, la primera fila salia MUTILADA en las 4 etiquetas de la
# prueba fisica -- del wordmark, el SKU y el precio quedaban solo los trazos
# inferiores. No era falta de tinta: la impresora ya estaba en darkness 30/30
# con transferencia termica. Era registro. Al calibrarla (~JC) aparecio la
# causa: el papel mide 112 dots, no 114, asi que todo el layout venia dibujado
# sobre 2 dots que no existen, y el margen de arriba (el mas chico) era el que
# se pasaba de rosca. Recentrar parejo sobre la medida real tolera el desfase
# para los dos lados, en vez de apostar a uno.
Y_TOP_BAND = 20        # el precio, que es el bloque mas alto de la banda 1
Y_LOGO_SKU = 23        # wordmark y SKU, bajados para que apoyen con el precio
Y_NAME = 48
Y_SPEC = 76

FONT_SKU = (18, 13)
FONT_PRICE = (24, 19)  # el ancho se achica solo si el importe es largo
FONT_NAME = (24, 13)   # el ANCHO era lo que la dejaba condensada, no el alto
FONT_SPEC = (16, 11)

# La fuente A0 es escalable y PROPORCIONAL: cada caracter ocupa bastante menos
# que el ancho nominal (una "i" mucho menos que una "W"). Medido contra el
# render real de la etiqueta, el promedio ronda el 65% del nominal.
CHAR_W_RATIO = 0.65

SPEC_SEP = " | "


def _text_w(text, char_w):
    """Ancho aproximado en dots que ocupa un texto con ese ancho nominal."""
    return len(text) * char_w * CHAR_W_RATIO


def _fit(text, avail_dots, char_w):
    """Recorta el texto a los caracteres que entran en el ancho disponible."""
    if not text:
        return ""
    return text[: max(0, int(avail_dots / (char_w * CHAR_W_RATIO)))]


def _zpl_safe(text):
    """`^` y `~` son los prefijos de comando de ZPL: en un ^FD parten la etiqueta."""
    return (text or "").replace("^", " ").replace("~", " ")


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

    def _get_label_spec_line(self):
        """La banda 3: la ficha en un renglon, agrupada por sentido.

        Cada grupo se arma solo con los datos que existen y los grupos vacios no
        aportan separador -- por eso el renglon nunca queda con huecos.
        """
        self.ensure_one()
        attr_map = self._get_attribute_map()
        specs = self._get_stone_specs(attr_map)
        metal = attr_map.get("Material") or attr_map.get("Primary Color", "")
        metal = METAL_ABBR.get(metal, metal)
        origin = attr_map.get("Diamond Origin") or attr_map.get("Center Diamond Origin", "")

        quantity = specs.get("quantity", "")
        carat = " ".join(v for v in (
            specs.get("carat", ""), ("x%s" % quantity) if quantity else "") if v)
        piedra = " ".join(v for v in (
            carat, specs.get("clarity", ""), specs.get("color", ""), origin) if v)
        aleacion = " ".join(v for v in (attr_map.get("Karatage", ""), metal) if v)
        medida = " ".join(v for v in (
            self._first_of(attr_map, MEASURE_ATTRS),
            self._first_of(attr_map, CLASP_ATTRS)) if v)
        return SPEC_SEP.join(v for v in (piedra, aleacion, medida) if v)

    def get_jewelry_label_zpl(self):
        self.ensure_one()
        sku = _zpl_safe(self.default_code or "")
        name = _zpl_safe(self.name or "")
        spec = _zpl_safe(self._get_label_spec_line())
        price = "$ {:,.2f}".format(self.lst_price)

        # El precio se achica solo si el importe es largo, para que no se le
        # monte al SKU centrado (una pieza de seis cifras los hacia chocar).
        price_h, price_w = FONT_PRICE
        sku_half = _text_w(sku, FONT_SKU[1]) / 2.0
        while price_w > 12 and (
                X0 + USABLE_W / 2.0 + sku_half + 8 > X1 - _text_w(price, price_w)):
            price_w -= 1

        return (
            "^XA"
            "^PW{width}^LL{height}"
            # Banda 1: wordmark, SKU centrado y precio alineado a la derecha.
            # El centrado y la alineacion los hace ^FB sobre el ancho util, asi
            # el SKU queda al medio sea cual sea el largo del codigo.
            "^FO{x0},{y_logo}{logo}^FS"
            "^FO{x0},{y_logo}^A0N,{skuh},{skuw}^FB{usable},1,0,C^FD{sku}^FS"
            "^FO{x0},{y_top}^A0N,{ph},{pw}^FB{usable},1,0,R^FD{price}^FS"
            # Banda 2: que es la pieza, a lo ancho. ^FB corta por palabra, no a
            # mitad de palabra, y admite una segunda linea para nombres largos.
            "^FO{x0},{y_name}^A0N,{nh},{nw}^FB{usable},2,1,L^FD{name}^FS"
            # Banda 3: la ficha.
            "^FO{x0},{y_spec}^A0N,{sh},{sw}^FD{spec}^FS"
            "^XZ"
        ).format(
            width=LABEL_WIDTH_DOTS,
            height=LABEL_HEIGHT_DOTS,
            x0=X0,
            usable=USABLE_W,
            y_logo=Y_LOGO_SKU,
            y_top=Y_TOP_BAND,
            y_name=Y_NAME,
            y_spec=Y_SPEC,
            logo=LOGO_ZPL,
            sku=sku,
            skuh=FONT_SKU[0], skuw=FONT_SKU[1],
            price=price,
            ph=price_h, pw=price_w,
            name=name,
            nh=FONT_NAME[0], nw=FONT_NAME[1],
            spec=_fit(spec, USABLE_W, FONT_SPEC[1]),
            sh=FONT_SPEC[0], sw=FONT_SPEC[1],
        )
