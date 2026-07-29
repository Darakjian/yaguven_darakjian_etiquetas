from odoo import models

# El wordmark (logo_zpl.LOGO_ZPL) se saco del layout a pedido de la tienda el 2026-07-29 para
# liberar espacio. El modulo se deja disponible por si se decide volver a incluirlo.

# Prioridad de familia de piedra: la primera que tenga "Carat Weight" cargado
# es la que se usa para armar la etiqueta. Agregadas 2026-07-29 (hallazgo del
# formato nuevo): "Side Diamond", "Marquis Diamond" y "Round Diamond" -- 10
# piezas del catalogo tienen SOLO estas familias cargadas y la ficha salia sin
# piedra. Si una pieza tiene mas de una familia (ej. Center + Side), se
# muestra la de mayor prioridad en esta lista, no ambas.
STONE_FAMILIES = [
    "Center Diamond",
    "Diamond",
    "Gem",
    "Accent Stone",
    "Sapphire",
    "Ruby",
    "Emerald",
    "Side Diamond",
    "Marquis Diamond",
    "Round Diamond",
]

# Casos irregulares: el atributo de carat/cantidad de esa familia NO sigue el
# patron estandar "<familia> Carat Weight" / "<familia> Quantity".
CARAT_ATTR_OVERRIDE = {
    "Marquis Diamond": "Marquis Diamond Weight",
    "Round Diamond": "Round Diamond Weight",
}
QUANTITY_ATTR_OVERRIDE = {
    "Marquis Diamond": "Marquis Quantity",
}

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

# LIENZO (^PW) vs CONTENIDO (X0/X1/USABLE_W): son DOS cosas distintas y ahi estuvo el bug.
#
# CANVAS_WIDTH_DOTS = el ancho que se le declara a la impresora = el tag ENTERO (3 1/2in @203dpi).
# Declarar 355 (solo la paleta) hacia que el bloque NO quedara anclado al margen izquierdo real del
# tag: se probo toda una escalera de zpl.left_position (0, -10, -130, -150, -175, -200) sin resultado
# estable. Con el lienzo del tag completo y left_position=0, el contenido apoya contra el margen
# izquierdo de forma estable. Confirmado en la tienda 2026-07-29 ("esa es la que va").
CANVAS_WIDTH_DOTS = 710

# CONTENT_WIDTH_DOTS = el ancho sobre el que se DIBUJA la ficha = la paleta imprimible (1 3/4in).
# NO subir esto a 710: el ^FB centra/alinea sobre este ancho, asi que agrandarlo correria el SKU al
# centro del tag entero y el precio a la punta de la cola de enganche.
CONTENT_WIDTH_DOTS = 355

LABEL_HEIGHT_DOTS = 112  # MEDIDO: calibracion ~JC del 27/07 -> zpl.label_length
                         # bajo de 0114 a 0112. Los 114 anteriores venian de la
                         # impresora SIN calibrar: el papel real mide 112 dots.

X0 = 10                              # margen lateral, parejo de los dos lados
X1 = CONTENT_WIDTH_DOTS - X0
USABLE_W = X1 - X0                   # 335 dots de ancho util

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
# Y hay un efecto colateral que justifica el cambio por si solo: usando el ancho
# entero de la paleta en vez de los ~200 de una columna derecha, las descripciones
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

FONT_SKU = (22, 16)    # agrandada al sacar el wordmark (2026-07-29): el SKU es el dato
                       # que la tienda busca primero y ahora tiene el lugar libre
FONT_PRICE = (24, 19)  # el ancho se achica solo si el importe es largo
FONT_NAME = (24, 13)   # el ANCHO era lo que la dejaba condensada, no el alto
FONT_SPEC = (16, 10)   # condensada: con la paleta de 355 el ancho util bajo a
                       # 335 dots y la ficha se cortaba ("| Size" sin la medida)

# La fuente A0 es escalable y PROPORCIONAL: cada caracter ocupa bastante menos que el ancho
# nominal (una "i" mucho menos que una "W"). MEDIDO sobre el render real (2026-07-29,
# _calibrar_char_ratio.py): texto de ficha 0.434-0.439, precios 0.426-0.430, SKUs 0.469-0.486.
# El 0.65 anterior estaba muy por encima de la realidad y hacia que _fit() recortara las fichas
# a 51 caracteres cuando en 335 dots entran ~76: 6,4% de las etiquetas salian cortadas a mitad de
# palabra ("Box w/ Hi", "18k Black Rhodi"). Se usa 0.50, apenas arriba del peor caso medido (SKUs
# en mayuscula), que es el texto que alimenta la guarda de colision SKU/precio.
#
# Ojo: esto sigue siendo una ESTIMACION y el peor caso teorico es mucho peor (una cadena de "W"
# mide 0.81). Por eso la ficha ya NO se recorta con esta cuenta: se deja que el ^FB de la impresora
# la ajuste con la metrica real de la fuente (ver get_jewelry_label_zpl). El ratio queda solo para
# la guarda del precio, donde un desvio chico no pierde informacion.
CHAR_W_RATIO = 0.50

SPEC_SEP = " | "


def _text_w(text, char_w):
    """Ancho aproximado en dots que ocupa un texto con ese ancho nominal."""
    return len(text) * char_w * CHAR_W_RATIO


def _fit(text, avail_dots, char_w):
    """Recorta el texto a los caracteres que entran en el ancho disponible.

    YA NO SE USA para la ficha (la ajusta ^FB con la metrica real). Se conserva por si algun
    campo futuro necesita un recorte duro.
    """
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
            carat_attr = CARAT_ATTR_OVERRIDE.get(family, "%s Carat Weight" % family)
            carat = attr_map.get(carat_attr)
            if carat:
                qty_attr = QUANTITY_ATTR_OVERRIDE.get(family, "%s Quantity" % family)
                return {
                    "carat": carat,
                    "clarity": attr_map.get("%s Clarity" % family, ""),
                    "color": attr_map.get("%s Color" % family, ""),
                    "quantity": attr_map.get(qty_attr, ""),
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
            # ^PW = el tag ENTERO; el contenido se dibuja sobre USABLE_W (la paleta)
            # y por eso queda apoyado contra el margen izquierdo.
            "^PW{width}^LL{height}"
            # Banda 1: SKU centrado y precio alineado a la derecha. El wordmark se
            # saco a pedido de la tienda (2026-07-29) para liberar espacio; el SKU
            # ocupa ese lugar con fuente mas grande.
            "^FO{x0},{y_logo}^A0N,{skuh},{skuw}^FB{usable},1,0,C^FD{sku}^FS"
            "^FO{x0},{y_top}^A0N,{ph},{pw}^FB{usable},1,0,R^FD{price}^FS"
            # Banda 2: que es la pieza, a lo ancho. ^FB corta por palabra, no a
            # mitad de palabra, y admite una segunda linea para nombres largos.
            "^FO{x0},{y_name}^A0N,{nh},{nw}^FB{usable},2,1,L^FD{name}^FS"
            # Banda 3: la ficha. ^FB (no recorte por cuenta propia): la impresora la ajusta con
            # la metrica REAL de la fuente y corta por palabra, nunca a mitad de dato. Admite una
            # 2da linea para las fichas muy largas, que antes se perdian.
            "^FO{x0},{y_spec}^A0N,{sh},{sw}^FB{usable},2,0,L^FD{spec}^FS"
            "^XZ"
        ).format(
            width=CANVAS_WIDTH_DOTS,
            height=LABEL_HEIGHT_DOTS,
            x0=X0,
            usable=USABLE_W,
            y_logo=Y_LOGO_SKU,
            y_top=Y_TOP_BAND,
            y_name=Y_NAME,
            y_spec=Y_SPEC,
            sku=sku,
            skuh=FONT_SKU[0], skuw=FONT_SKU[1],
            price=price,
            ph=price_h, pw=price_w,
            name=name,
            nh=FONT_NAME[0], nw=FONT_NAME[1],
            spec=spec,
            sh=FONT_SPEC[0], sw=FONT_SPEC[1],
        )
