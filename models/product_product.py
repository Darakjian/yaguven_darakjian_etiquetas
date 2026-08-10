import base64
import hashlib
import io
import logging

import requests
from markupsafe import Markup
from PIL import Image, ImageDraw

from odoo import _, models
from odoo.tools.misc import html_escape

_logger = logging.getLogger(__name__)

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

# --- GEOMETRIA DEL TAG ------------------------------------------------------
# LIENZO (^PW) vs CONTENIDO: son DOS cosas distintas y ahi estuvo el bug original.
#
# CANVAS_WIDTH_DOTS = el ancho que se le declara a la impresora = el tag ENTERO
# (3 1/2in @203dpi). Declarar solo la paleta hacia que el bloque NO quedara anclado al
# margen izquierdo real del tag: se probo toda una escalera de zpl.left_position
# (0, -10, -130, -150, -175, -200) sin resultado estable. Con el lienzo del tag completo
# y left_position=0 el contenido apoya contra el margen izquierdo de forma estable.
# Confirmado en la tienda 2026-07-29 ("esa es la que va").
CANVAS_WIDTH_DOTS = 710

# CONTENT_WIDTH_DOTS = la PALETA imprimible (1 3/4in). La mitad derecha del tag
# (dots ~355-710) NO es paleta: es la COLA DE ENGANCHE, una tira mas angosta que se
# enrolla en la joya y queda oculta (confirmado con la foto del troquel real del
# 2026-07-30). La ficha vive entera dentro de la paleta.
CONTENT_WIDTH_DOTS = 355

# --- LA COLA, MEDIDA SOBRE LA IMPRESION DEL 2026-08-06 ----------------------
# Registrando el ZPL desplegado contra la foto de las 4 etiquetas (anclando en el centro
# de tinta del SKU y del precio, que son dots conocidos) se recupero la geometria de la
# cola. El registro se valida solo: con esa misma escala el borde superior del papel cae
# en el dot -20 y el corte del troquel en el 105, que son los dos valores que ya estaban
# medidos por otra via.
#
#   - el escalon paleta/cola (la linea vertical) cae en el dot ~360, no en el 355;
#   - a la derecha de ese escalon hay papel SOLO entre los dots 15 y 104 -- 89 dots, que
#     es exactamente el 7/16in de la ficha del fabricante;
#   - y dentro de la cola hay DOS lineas de troquel horizontales que delimitan una
#     ventana de unos 20 dots.
#
# Esa ventana es la que importa: la descripcion cruza a proposito el escalon (es lo que
# permite que entre en un renglon), asi que tiene que caer DENTRO de ella. Antes arrancaba
# en el dot 49, o sea justo ENCIMA de la linea de arriba, y en la foto se veia el troquel
# pasando por el medio del texto.
#
# LOS BORDES SE CORRIGIERON CON LA SEGUNDA IMPRESION (2026-08-06, 13:32). La primera medicion
# dio 49..68 y con esos valores la descripcion entro en la ventana pero pegada al techo: 1
# dot de aire arriba contra 6 abajo. Las dos etiquetas nuevas, registradas por separado,
# ponen las lineas en el 51 y el 71 -- y las dos devuelven el corte del troquel en el dot
# 106,7 contra el 107 del modelo, que es el control que dice que la escala esta bien.
COLA_TOP_DOTS = 51
COLA_BOT_DOTS = 71

# Borde fisico derecho del tag. Solo lo usa el ancho del bloque de identidad, que cruza
# la costura paleta/cola a proposito (ver COL_W).
TAG_RIGHT_EDGE_DOTS = 695

LABEL_HEIGHT_DOTS = 112  # el alto del LIENZO que le declaramos a la Zebra (^LL).
                         # OJO: no es el alto del papel. Ver PAPER_* aca abajo.

# --- EL PAPEL DE VERDAD, MEDIDO SOBRE LA FOTO DEL TROQUEL (2026-08-02) -------
# Registrando el ZPL contra las 3 etiquetas impresas de la foto de la tienda
# (_calibrar_modelo_sobre_foto.py, correlacion 0.75 en las tres) se midio que el troquel
# NO coincide con el lienzo:
#   - el papel avanza 127 dots por etiqueta, no 112;
#   - arranca en el dot -20, o sea ANTES del y=0 del ZPL: esa franja de papel existe pero
#     la impresora no la alcanza, se pierde;
#   - y el corte cae en el dot +107, o sea 5 ANTES del final del lienzo.
# Consecuencia practica: el limite de abajo no es el ^LL sino el corte del troquel, y hay
# 15 dots mas de papel util de los que el lienzo hacia suponer.
PAPER_TOP_DOTS = -20     # informativo: no se puede imprimir ahi
PAPER_CUT_DOTS = 107     # el corte del troquel: NINGUN campo puede pasar de aca

# LA LINEA DE PLEGADO. El tag trae un doblez vertical propio (se ve en las etiquetas
# virgenes de la tira, corre de corte a corte) en el punto medio exacto del bloque
# imprimible, que va del dot 5 al 357. Confirmado por la tienda: el tag SE DOBLA ahi.
# Es un limite duro: el texto que la cruza se quiebra en el pliegue y ademas queda
# repartido entre las dos caras del tag doblado. Por eso el pliegue se usa como FRONTERA
# de layout -- la ficha termina antes, el bloque de identidad empieza despues.
FOLD_DOTS = 182
FOLD_CLEARANCE = 6       # aire a cada lado del pliegue: el texto no apoya sobre la marca

X0 = 10                  # margen lateral, parejo de los dos lados

# MARGEN VERTICAL 20 arriba / 20 abajo, NO NEGOCIABLE. La prueba fisica del 30/07 salio
# con la primera linea MUTILADA (solo los trazos inferiores del SKU y de la primera fila
# de la ficha) porque la maqueta arrancaba en y=6/8 para meter una fila mas: el registro
# del papel se come esa franja. Recentrar parejo sobre el alto real tolera el desfase
# para los dos lados, en vez de apostar a uno.
#
# Consecuencia de diseno: el alto util no son 112 dots sino 72 (de y=20 a y=92). Por eso
# la ficha va en 4 filas y no en 5.
Y_TOP = 20
Y_BOT = LABEL_HEIGHT_DOTS - 20        # 92: ningun campo puede terminar mas abajo

# --- LAYOUT: ficha en TABLA a la izquierda + identidad a la derecha ----------
# Es la "alternativa A", que Armen eligio sobre la B el 2026-07-30 porque replica la
# disposicion de la etiqueta que la tienda ya usa hoy:
#
#   10.29Ct x40   Box w/ Hidden Safety     DBRE.00085376
#   VS            7.00"                    LAB GROWN 10.29Ctw Emerald Tennis Bracelet
#   G-H Color     14k                      $ 11,165.00
#   Lab Grown     YG
#
# RANURA FIJA: cada atributo tiene su celda reservada. Si la pieza no tiene ese dato la
# celda queda VACIA y ningun otro valor se corre de lugar. Ese era el defecto de la
# etiqueta heredada -- valores sin rotulo y con huecos, donde lo de abajo "subia" y el
# mismo renglon cambiaba de significado segun la pieza.
#
# Peso y cantidad van juntos en una celda ("0.62ct x41"), que es como se leen de todas
# formas: con 72 dots utiles entran 4 filas de 18, no 5.
GRID = [["carat_qty", "clasp"],
        ["clarity", "measure"],
        ["color", "karatage"],
        ["origin", "metal"]]
# LA FICHA SE AGRANDO de 14 a 17 de alto (pedido del usuario 2026-08-03: "que sea mas
# visible") SIN que el texto ocupe un dot mas de ancho. Se puede por como cuantiza el ^A0N:
# el ancho del glifo lo fija el parametro de ancho, no el alto, y esta escalonado --
# medido, los anchos 7, 8, 9 y 10 rinden todos lo mismo, y recien en 11 el texto crece.
# Asi que 17 de alto con 10 de ancho da letras un 21% mas altas y exactamente el mismo
# ancho que antes. Es gratis: no toca el pliegue ni obliga a repartir las columnas de nuevo.
#
# El paso de fila sube de 18 a 20 para mantener el aire entre renglones. Con eso la ficha
# ocupa 25..102, que es justo donde termina el precio: los dos bloques cierran parejos y
# quedan 5 dots hasta el corte del troquel, el mismo margen que le dimos al precio.
TABLE_ROW_STEP = 20
FONT_TABLE = (17, 10)

# LAS DOS COLUMNAS SE CORRIERON A LA IZQUIERDA (2026-08-03) para que la segunda termine
# ANTES del pliegue. Antes iban en 10..96 y 98..210: la segunda nacia de un lado del
# doblez y moria del otro, y "Box w/ Hidden Safety" ya llegaba al dot 183, justo encima
# de la marca.
#
# El ancho de la col 2 lo fija el peor caso REAL del catalogo, no la muestra: el valor de
# cierre mas largo es "Push Lock w/ Figure 8" = 88 dots (medido sobre el render, no
# estimado). Y no se puede achicar condensando la fuente: 9, 8 y 7 de ancho dan los
# mismos 88 dots -- el parametro de ancho del ^A0N toca fondo y deja de condensar.
# Asi que la col 2 necesita 88 dots si o si, y de ahi sale donde tiene que arrancar:
#     fin = FOLD_DOTS - FOLD_CLEARANCE = 176   ->   inicio = 176 - 88 = 88
# A la col 1 le quedan 76 dots (10..86). Alcanza de sobra: su valor mas ancho medido en
# el catalogo es de 45 dots.
#
# Lo que NO resuelve esto: los metales sin abreviar ("Black & Carnation & Grey & Yellow",
# 139 dots) siguen sin entrar. Ya no entraban antes -- no es una regresion de este cambio,
# pero queda anotado como pendiente aparte.
TABLE_COLS_X = [0, 78]                # col 1: la piedra. col 2: medida y aleacion
TABLE_COL_W = [76, 88]

# La ficha baja 5 dots respecto del margen general (pedido del usuario 2026-08-03). Tiene
# constante propia y no se toca Y_TOP: Y_TOP tambien gobierna el SKU, asi que moverlo
# bajaria de arrastre la columna de identidad, que ya esta donde tiene que estar.
TABLE_NUDGE = 5
TABLE_TOP = Y_TOP + TABLE_NUDGE       # 25

# Bloque de identidad: SKU, descripcion y precio APILADOS, los tres arrancando en la
# MISMA columna (pedido de Gabriel por audio, 2026-07-31; antes la descripcion iba en una
# columna aparte, sobre la cola).
#
# Se corrio de 214 a 188 (2026-08-03) para que apoye contra el pliegue en vez de dejar un
# hueco muerto de 32 dots. Es lo que marco Gabriel en azul sobre la foto: su marca cae
# justo en ese hueco (dots 184..212), no sobre la columna.
COL_X = FOLD_DOTS + FOLD_CLEARANCE            # 188: pegado al pliegue, del lado de afuera

# El ancho NO se limita a los 131 dots de paleta que quedan a la derecha: se extiende
# hasta el borde real del tag, cruzando a proposito la costura paleta/cola. Eso es lo que
# permite que una descripcion larga entre en UN solo renglon sin achicarle la fuente. El
# ^PW710 ya ancla el bloque al margen izquierdo, asi que no corre nada del resto.
COL_W = TAG_RIGHT_EDGE_DOTS - COL_X

# EL SKU NO VA EN LA FUENTE ESCALABLE (2026-08-05). La `A0` es la unica proporcional y
# escalable de la Zebra, y a este cuerpo CONDENSA EL TRAZO: los digitos se empastan y se
# leen montados. Es lo que Gabriel viene marcando desde el 04/08, y no se arregla con
# tamano -- se probaron 18,13 / 22,13 / 22,15 / 24,13 y el defecto sigue. Hay que salir de
# la familia escalable.
#
# Se imprimieron tres demos fisicas con el mismo SKU y Armen eligio la primera (fuente D,
# `^ADN,18,10`), pidiendola un 20% mas chica. LA D NO SE PUEDE ACHICAR: las bitmap de paso
# fijo no bajan de su tamano base -- `^ADN,14,8` devuelve un render IDENTICO al de
# `^ADN,18,10` (153x14 dots, medido en Labelary). El escalon siguiente hacia abajo dentro
# de la familia es la B, y ahi se fue el 2026-08-05.
#
# EN PAPEL LA B QUEDO CHICA (2026-08-06). La tira que mando la tienda trae las dos: las dos
# de abajo salieron con la escalable vieja y las dos de arriba con la B. Medido sobre la
# foto contra el alto del precio, la B rinde 0,64 de esa referencia contra 0,80 de la
# escalable -- o sea que al salir del empastado tambien se perdio cuerpo. La familia quedo
# confirmada (la B se lee digito por digito donde la escalable montaba el "526"); lo que
# faltaba era volver al tamano.
#
# LA D NO SIRVE, AUNQUE FUERA LA ELEGIDA: se probo (`^ADN,18,10`) y en el papel el SKU de
# 15 caracteres termina en el dot 364 con el escalon paleta/cola en el 360 -- toca el
# troquel. Y no es un caso raro: de 24.388 variantes con SKU en v19, el **51,5% tiene 15
# caracteres** y el 43,6% tiene 13. El requisito de la tienda es que el SKU no toque el
# troquelado de ningun lado, asi que la D queda descartada por ancho, no por dibujo.
#
# LA SALIDA: LAS BITMAP ESCALAN ALTO Y ANCHO POR SEPARADO. Medido en Labelary, `^ABN,22,7`
# es la B con el ALTO duplicado y el ancho SIN tocar -- no es lo mismo que `^ABN,22,14`,
# que duplica las dos cosas y se come la cola. Los multiplicadores son enteros y cada eje
# va por su cuenta; un valor que no sea multiplo se redondea para abajo (`^ABN,16,7`
# dibuja igual que `^ABN,11,7`).
#
#   fuente        alto de tinta   ancho 16 car.   termina en el dot
#   B 11,7             11              142              329
#   D 18,10            14              188              376   <- toca el escalon (360)
#   B 22,7             22              142              329   <- 31 dots de aire
#
# O sea: mas alto que la D y con el ancho de la B. El costo es la proporcion -- los glifos
# quedan estirados 2:1, altos y angostos. Es el precio de que entre siempre.
FONT_SKU = (22, 7)
FONT_SKU_CMD = "ABN"

FONT_DESC = (14, 8)
FONT_PRICE = (24, 18)

# EL PRECIO SE BAJA hasta apoyar contra el corte del troquel (pedido de Gabriel del
# 2026-08-01, la marca verde sobre la foto). Ya no se cuelga del Y_BOT del lienzo: se
# cuelga del PAPEL medido, que es el limite que importa. La marca verde de Gabriel arranca
# en el dot 78 y este calculo cae exactamente ahi -- la marca y la medicion coinciden solas.
PRICE_SAFETY = 5         # aire entre el pie del precio y el corte del troquel

Y_SKU = Y_TOP + 2
Y_PRICE = PAPER_CUT_DOTS - PRICE_SAFETY - FONT_PRICE[0]      # 78

# LA DESCRIPCION SE CUELGA DE LA COLA, NO DEL HUECO (2026-08-06). Venia centrada en el
# espacio libre entre el SKU y el precio, que es un criterio de la PALETA -- y la
# descripcion es el unico campo que sale de la paleta y sigue sobre la cola. Con las dos
# lineas de troquel de la cola ya medidas (dots 49 y 68), el centrado bueno es el de esa
# ventana: asi el pedazo que queda afuera de la paleta cae dentro del recuadro en vez de
# montarse sobre el corte.
#
# Lo de antes dejaba la tinta en 49..59, o sea apoyada JUSTO sobre la linea de arriba: en
# la foto del 06/08 se ve el troquel cruzando el texto de lado a lado. Centrada da 53..63,
# con 4 dots de aire de cada lado.
#
# El cuerpo de la fuente no es el alto de la tinta: la `A0N,14,8` dibuja 11 dots y los
# arranca UNO ARRIBA del ^FO (las dos cosas medidas en Labelary). Se centra la TINTA, que
# es lo que se ve, y despues se convierte a coordenada de ^FO.
DESC_INK_H = 11
DESC_INK_OFFSET = -1

# DESC_NUDGE: el centro GEOMETRICO no es el que se ve centrado. Con la ventana en 51..71 el
# calculo deja la tinta en 55..65 y sobre el papel se lee alta -- pedido de la tienda del
# 2026-08-06: "que baje 2 dots". Coincide con la medicion: los picos de las dos lineas de
# troquel salieron en {50, 51, 53} y {70, 72, 73}, o sea que la ventana real esta un par de
# dots mas abajo que el punto medio de esos grupos. Se corrige con el corrimiento y no
# cableando el valor, para no perder el centrado automatico si cambia la fuente.
DESC_NUDGE = 2
Y_DESC = (COLA_TOP_DOTS + (COLA_BOT_DOTS - COLA_TOP_DOTS - DESC_INK_H) // 2
          - DESC_INK_OFFSET + DESC_NUDGE)


def _zpl_safe(text):
    """`^` y `~` son los prefijos de comando de ZPL: en un ^FD parten la etiqueta."""
    return (text or "").replace("^", " ").replace("~", " ")


def _field(x, y, font, text, width, lines=1, align="L", cmd="A0N"):
    """Un campo de texto.

    El ancho se resuelve con ^FB, o sea que lo ajusta LA IMPRESORA con la metrica real de
    la fuente y cortando por palabra. No recortamos por cuenta propia: esa cuenta (una
    estimacion de ancho por caracter) fue la que cortaba las fichas a mitad de palabra
    -- "Box w/ Hi", "18k Black Rhodi".

    `cmd` es la fuente. Por defecto la escalable `A0N`, que es la que usan la ficha, la
    descripcion y el precio. Solo el SKU pasa otra (ver FONT_SKU_CMD): la escalable le
    empasta los digitos.
    """
    if not text:
        return ""
    return "^FO%d,%d^%s,%d,%d^FB%d,%d,1,%s^FD%s^FS" % (
        x, y, cmd, font[0], font[1], width, lines, align, _zpl_safe(text))


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

    def _get_label_cells(self):
        """Los valores de la ficha SUELTOS, uno por celda de la tabla.

        El layout en ranura fija necesita cada dato por separado para poder darle su
        posicion reservada; el renglon corrido del layout anterior (piedra | aleacion |
        medida, todo concatenado) no servia para esto.
        """
        self.ensure_one()
        attr_map = self._get_attribute_map()
        specs = self._get_stone_specs(attr_map)
        metal = attr_map.get("Material") or attr_map.get("Primary Color", "")
        carat = specs.get("carat", "")
        quantity = specs.get("quantity", "")
        return {
            "carat_qty": carat + ((" x%s" % quantity) if carat and quantity else ""),
            "clarity": specs.get("clarity", ""),
            "color": specs.get("color", ""),
            "origin": (attr_map.get("Diamond Origin")
                       or attr_map.get("Center Diamond Origin", "")),
            "karatage": attr_map.get("Karatage", ""),
            "metal": METAL_ABBR.get(metal, metal),
            "measure": self._first_of(attr_map, MEASURE_ATTRS),
            "clasp": self._first_of(attr_map, CLASP_ATTRS),
        }

    def get_jewelry_label_zpl(self):
        self.ensure_one()
        cells = self._get_label_cells()

        zpl = ["^XA^PW%d^LL%d" % (CANVAS_WIDTH_DOTS, LABEL_HEIGHT_DOTS)]
        for i, row in enumerate(GRID):
            for j, field in enumerate(row):
                zpl.append(_field(X0 + TABLE_COLS_X[j], TABLE_TOP + TABLE_ROW_STEP * i,
                                  FONT_TABLE, cells.get(field, ""), TABLE_COL_W[j]))
        zpl.append(_field(COL_X, Y_SKU, FONT_SKU, self.default_code or "", COL_W,
                          cmd=FONT_SKU_CMD))
        zpl.append(_field(COL_X, Y_DESC, FONT_DESC, self.name or "", COL_W))
        zpl.append(_field(COL_X, Y_PRICE, FONT_PRICE,
                          "$ {:,.2f}".format(self.lst_price), COL_W))
        zpl.append("^XZ")
        return "".join(zpl)

    # --- VISTA PREVIA EN EL CHATTER -----------------------------------------
    # Lo que se imprime se registra en el chatter de la variante con la imagen de la
    # etiqueta SOBRE EL TROQUEL. Sin el troquel dibujado la imagen enganha: el render
    # crudo del ZPL muestra un lienzo de 112 dots que no existe en el papel, no dice
    # donde cae el corte ni donde se dobla el tag, y son justo los dos limites contra
    # los que se valida un layout.

    LABELARY_URL = "http://api.labelary.com/v1/printers/8dpmm/labels/3.5x0.55/0/"
    PREVIEW_SCALE = 4          # 1 px por dot es ilegible en pantalla; 4x da 2840x508
    PREVIEW_LEGEND_H = 108     # banda de abajo para los rotulos

    def _legend_font(self):
        """La fuente por defecto de PIL mide 11px y sobre un lienzo de 2840 no se lee. Se
        usa DejaVu, que esta en la imagen de Odoo.sh (verificado), con fallback por si
        manana no esta: la vista previa no puede caerse por una tipografia."""
        from PIL import ImageFont
        for ruta in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"):
            try:
                return ImageFont.truetype(ruta, 26)
            except OSError:
                continue
        return ImageFont.load_default()

    def _labelary_png(self, zpl):
        """Rasteriza el ZPL con Labelary: es un interprete ZPL real, asi que el PNG es
        lo que sale por la Zebra y no una aproximacion nuestra. Devuelve None si el
        servicio no responde -- el registro de la impresion no depende de la imagen."""
        try:
            r = requests.post(self.LABELARY_URL, data=zpl.encode("utf8"), timeout=10)
            r.raise_for_status()
            return r.content
        except Exception as e:
            _logger.warning("Labelary no pudo rasterizar la etiqueta: %s", e)
            return None

    def _draw_die_cut(self, png_bytes):
        """Pega el render sobre el papel REAL y le dibuja el troquel encima.

        El render viene con el lienzo del ZPL (y=0..111). El papel no coincide: arranca
        en el dot -20 (esa franja existe pero el cabezal no la alcanza) y el corte cae
        en el +107. Por eso el render se corta en 107 y se pega 20 dots mas abajo: asi
        las coordenadas de la imagen son las del PAPEL, no las del lienzo.

        Codigo de color daltonico-seguro (azul/naranja, nunca verde/rojo): AZUL el borde
        del troquel y la costura de la cola, NARANJA el pliegue -- que es el unico limite
        que rompe el texto en dos caras y conviene que salte a la vista.
        """
        render = Image.open(io.BytesIO(png_bytes)).convert("L")
        alto_papel = PAPER_CUT_DOTS - PAPER_TOP_DOTS          # 127
        desplaz = -PAPER_TOP_DOTS                             # 20

        papel = Image.new("L", (CANVAS_WIDTH_DOTS, alto_papel), 255)
        papel.paste(render.crop((0, 0, CANVAS_WIDTH_DOTS,
                                 min(PAPER_CUT_DOTS, render.height))), (0, desplaz))

        s = self.PREVIEW_SCALE
        # NEAREST y no bicubico: cada dot tiene que verse como el cuadrado que es. Suavizar
        # la escala inventa grises y hace parecer legible un texto que en el papel no lo es.
        out = papel.resize((CANVAS_WIDTH_DOTS * s, alto_papel * s),
                           Image.NEAREST).convert("RGB")
        lienzo = Image.new("RGB", (out.width, out.height + self.PREVIEW_LEGEND_H), "white")
        lienzo.paste(out, (0, 0))
        d = ImageDraw.Draw(lienzo)

        AZUL, NARANJA, GRIS = (0, 82, 155), (214, 106, 0), (150, 150, 150)

        # Franja de arriba que el cabezal no alcanza: se raya para que no se confunda con
        # papel util. Es de donde salio el "esta impreso muy alto" que la tienda veia.
        for x in range(0, lienzo.width, 12):
            d.line([(x, 0), (x + desplaz * s, desplaz * s)], fill=GRIS, width=1)
        d.line([(0, desplaz * s), (lienzo.width, desplaz * s)], fill=GRIS, width=2)

        d.rectangle([(0, 0), (out.width - 1, out.height - 1)], outline=AZUL, width=3)

        for x_dot, color, ancho in ((FOLD_DOTS, NARANJA, 3),
                                    (CONTENT_WIDTH_DOTS, AZUL, 2)):
            x = x_dot * s
            for y in range(0, out.height, 16):     # punteada: no tapa lo que hay debajo
                d.line([(x, y), (x, y + 8)], fill=color, width=ancho)

        fuente = self._legend_font()
        base = out.height + 10
        for i, (texto, color) in enumerate((
            ("BLUE: die-cut edge (cut at dot %d) and hang-tail seam (dot %d, which rolls "
             "up and stays hidden)"
             % (PAPER_CUT_DOTS, CONTENT_WIDTH_DOTS), AZUL),
            ("ORANGE: fold line (dot %d) -- anything crossing it is split between the "
             "two faces of the tag" % FOLD_DOTS, NARANJA),
            ("HATCHED: the %d dots of paper the printhead cannot reach (they start "
             "above y=0)" % desplaz, GRIS),
        )):
            d.text((10, base + i * 32), texto, fill=color, font=fuente)

        buf = io.BytesIO()
        lienzo.save(buf, format="PNG")
        return buf.getvalue()

    def _label_preview_attachment(self, zpl):
        """Adjunto de la vista previa, cacheado por hash del ZPL: mientras la etiqueta no
        cambie no se vuelve a pedir el render, aunque se imprima diez veces."""
        self.ensure_one()
        firma = hashlib.sha256(zpl.encode("utf8")).hexdigest()[:12]
        nombre = "tag_%s_%s.png" % (self.default_code or self.id, firma)
        Att = self.env["ir.attachment"]
        att = Att.search([("res_model", "=", "product.product"),
                          ("res_id", "=", self.id), ("name", "=", nombre)], limit=1)
        if att:
            return att
        crudo = self._labelary_png(zpl)
        if not crudo:
            return Att
        return Att.create({
            "name": nombre,
            "res_model": "product.product",
            "res_id": self.id,
            "mimetype": "image/png",
            "datas": base64.b64encode(self._draw_die_cut(crudo)),
        })

    def action_log_printed_label(self):
        """La llama el boton DESPUES de que el bridge confirmo la impresion. Se postea lo
        que efectivamente salio en papel; los intentos fallidos no ensucian el chatter."""
        self.ensure_one()
        zpl = self.get_jewelry_label_zpl()
        att = self._label_preview_attachment(zpl)

        cuerpo = "<p><strong>%s</strong> &mdash; %s</p>" % (
            html_escape(_("Tag printed")),
            html_escape(self.default_code or self.display_name))
        if not att:
            cuerpo += "<p>%s</p>" % html_escape(_(
                "The tag came out of the printer, but the preview could not be built "
                "(the rendering service did not answer)."))
        self.message_post(
            body=Markup(cuerpo),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
            attachment_ids=att.ids,
        )
        return True
