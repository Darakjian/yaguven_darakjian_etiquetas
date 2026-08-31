import base64
import hashlib
import io
import logging

import requests
from markupsafe import Markup
from PIL import Image, ImageDraw

from odoo import _, api, fields, models
from odoo.tools.misc import html_escape

_logger = logging.getLogger(__name__)

# The wordmark (logo_zpl.LOGO_ZPL) was pulled from the layout at the store's request on
# 2026-07-29 to free up room. The module is kept around in case it goes back in.

# Stone family priority: the first one with a "Carat Weight" filled in is the one used to
# build the tag. Added on 2026-07-29 while working through the new format: "Side Diamond",
# "Marquis Diamond" and "Round Diamond" -- 10 pieces in the catalog carry ONLY these
# families, and their spec block was coming out with no stone at all. When a piece has more
# than one family (Center + Side, say), the highest one in this list wins; not both.
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

# The odd ones out: for these families the carat/quantity attribute does NOT follow the
# standard "<family> Carat Weight" / "<family> Quantity" pattern.
CARAT_ATTR_OVERRIDE = {
    "Marquis Diamond": "Marquis Diamond Weight",
    "Round Diamond": "Round Diamond Weight",
}
QUANTITY_ATTR_OVERRIDE = {
    "Marquis Diamond": "Marquis Quantity",
}

# Fallback cascades: the first one carrying a value is the one printed. These attributes
# are mutually exclusive by piece type - a ring has a Ring Size, a necklace has a Length -
# which is why no single one of them is enough on its own.
# `Case Diameter` added on 2026-08-28: a watch calls its measurement that, and the tag
# was printing nothing in the Measure cell for the entire Watches branch. Reported by
# Gabriel from the counter -- Armen had pieces whose tag showed a single attribute.
MEASURE_ATTRS = ["Ring Size", "Length", "Drop Length", "Width", "Diameter",
                 "Case Diameter",
                 "Shank Width (M)", "Bracelet/Strap Length", "Gram Weight"]
CLASP_ATTRS = ["Clasp", "Earring Back", "Case Back"]

# PER-FAMILY SLOTS (2026-08-31). The eight cells were laid out for a ring with stones:
# carat, clarity, colour, diamond origin. A watch has none of those, so four cells printed
# blank for the whole branch WHILE the data a watch does carry -- dial colour, movement,
# what it is worn on -- had nowhere to go. Measured over the 2,921 watch templates: with
# the jewellery slots only 3 watches print four cells or more; with the slots below, 419
# do, and 155 of them print seven of the eight. No data is loaded to get that: it is the
# same attributes, read into cells that mean something for a watch.
#
# The grid does not move. What changes is WHICH attribute owns each cell, decided by the
# product's category. A family with no entry here keeps the jewellery slots, so nothing
# that works today can break: the mapping is additive.
FAMILY_SLOTS = {
    "watches": {
        # cell        candidates, first one carrying a value wins
        "carat_qty": ["Movement"],
        "clarity":   ["Bracelet/Strap Material"],
        "color":     ["Dial Color"],
        "origin":    ["Bracelet/Strap"],
    },
}
# How a piece is placed in a family: by its category path, longest match first so a more
# specific rule could be added later without reordering the dictionary.
FAMILY_BY_CATEGORY = {
    "Watch": "watches",
}
# The captions the screen prints for each cell, to explain a reuse in the words the user
# is reading on the form.
CELL_CAPTION = {"carat_qty": "Carat / Qty", "clarity": "Clarity", "color": "Color",
                "origin": "Origin", "clasp": "Clasp", "measure": "Measure",
                "karatage": "Karatage", "metal": "Metal"}

# The metal goes abbreviated, matching the tag the store already uses ("YG").
METAL_ABBR = {
    "White Gold": "WG", "Yellow Gold": "YG", "Rose Gold": "RG",
    "Pink Gold": "PG", "Two Tone": "2T", "Tri Color": "3T",
    "Platinum": "PLT", "Palladium": "PD", "Titanium": "TI",
    "Sterling Silver": "SS", "Silver": "SLV", "Stainless Steel": "STL",
}

# --- TAG GEOMETRY -----------------------------------------------------------
# CANVAS (^PW) vs CONTENT: these are TWO different things, and that is where the original
# bug lived.
#
# CANVAS_WIDTH_DOTS = the width declared to the printer = the WHOLE tag (3 1/2in @203dpi).
# Declaring only the paddle left the block unanchored from the tag's real left margin: a
# whole ladder of zpl.left_position values was tried (0, -10, -130, -150, -175, -200) with
# no stable result. With the full tag as the canvas and left_position=0, the content rests
# against the left margin consistently. Confirmed at the store on 2026-07-29 ("that's the
# one").
CANVAS_WIDTH_DOTS = 710

# CONTENT_WIDTH_DOTS = the printable PADDLE (1 3/4in). The right half of the tag (dots
# ~355-710) is NOT paddle: it is the HANG TAIL, a narrower strip that wraps around the
# piece and stays hidden (confirmed against the photo of the real die-cut on 2026-07-30).
# The spec block lives entirely inside the paddle.
CONTENT_WIDTH_DOTS = 355

# --- THE HANG TAIL, MEASURED AGAINST THE 2026-08-06 PRINT --------------------
# Registering the deployed ZPL against the photo of the 4 tags (anchoring on the ink centre
# of the SKU and of the price, both known dots) recovered the tail's geometry. The
# registration validates itself: at that same scale the top edge of the paper falls at dot
# -20 and the die-cut at 105, the two values already measured by other means.
#
#   - the paddle/tail step (the vertical line) falls at dot ~360, not at 355;
#   - to the right of that step there is paper ONLY between dots 15 and 104 -- 89 dots,
#     exactly the 7/16in on the manufacturer's spec sheet;
#   - and inside the tail there are TWO horizontal die lines bounding a window of some
#     20 dots.
#
# That window is what matters: the description crosses the step on purpose, which is what
# lets it fit on one line, so it has to land INSIDE the window. It used to start at dot 49,
# right ON TOP of the upper line, and the photo showed the die-cut running through the
# middle of the text.
#
# THE EDGES WERE CORRECTED WITH THE SECOND PRINT (2026-08-06, 13:32). The first measurement
# gave 49..68, and with those values the description did land in the window but pinned to
# the ceiling: 1 dot of air above against 6 below. The two new tags, registered separately,
# put the lines at 51 and 71 -- and both return the die-cut at dot 106.7 against the model's
# 107, which is the control confirming the scale is right.
COLA_TOP_DOTS = 51
COLA_BOT_DOTS = 71

# The tag's physical right edge. Only the width of the identity block uses it, and that
# block crosses the paddle/tail seam on purpose (see COL_W).
TAG_RIGHT_EDGE_DOTS = 695

LABEL_HEIGHT_DOTS = 112  # the height of the CANVAS declared to the Zebra (^LL).
                         # CAREFUL: not the height of the paper. See PAPER_* below.

# --- THE REAL PAPER, MEASURED ON THE DIE-CUT PHOTO (2026-08-02) --------------
# Registering the ZPL against the 3 printed tags in the store's photo
# (_calibrar_modelo_sobre_foto.py, correlation 0.75 on all three) showed the die-cut does
# NOT line up with the canvas:
#   - the paper advances 127 dots per tag, not 112;
#   - it starts at dot -20, that is BEFORE the ZPL's y=0: that strip of paper exists but
#     the printhead cannot reach it, so it is lost;
#   - and the cut falls at dot +107, 5 dots BEFORE the end of the canvas.
# What this means in practice: the bottom limit is the die-cut, not the ^LL, and there are
# 15 more dots of usable paper than the canvas suggested.
PAPER_TOP_DOTS = -20     # informational: nothing can be printed there
PAPER_CUT_DOTS = 107     # the die-cut: NO field may extend past this

# THE FOLD LINE. The tag carries a vertical fold of its own - visible on the blank tags in
# the strip, running cut to cut - at the exact midpoint of the printable block, which spans
# dots 5 to 357. Confirmed by the store: the tag IS folded there. It is a hard limit: text
# crossing it breaks at the fold and ends up split across the two faces of the folded tag.
# That is why the fold is used as a layout BOUNDARY - the spec block ends before it, the
# identity block starts after it.
FOLD_DOTS = 182
FOLD_CLEARANCE = 6       # air on each side of the fold: text never rests on the crease

X0 = 10                  # side margin, the same on both sides

# VERTICAL MARGIN 20 top / 20 bottom, NON-NEGOTIABLE. The physical test on 30/07 came out
# with the first line MUTILATED - only the lower strokes of the SKU and of the spec block's
# first row - because the mock-up started at y=6/8 to squeeze in one more row: the paper
# registration eats that strip. Recentring evenly over the real height absorbs the drift on
# both sides instead of betting on one.
#
# Design consequence: the usable height is not 112 dots but 72 (y=20 to y=92). That is why
# the spec block runs 4 rows and not 5.
Y_TOP = 20
Y_BOT = LABEL_HEIGHT_DOTS - 20        # 92: no field may end lower than this

# --- LAYOUT: spec block as a TABLE on the left, identity on the right --------
# This is "option A", which Armen picked over B on 2026-07-30 because it mirrors the layout
# of the tag the store already uses today:
#
#   10.29Ct x40   Box w/ Hidden Safety     DBRE.00085376
#   VS            7.00"                    LAB GROWN 10.29Ctw Emerald Tennis Bracelet
#   G-H Color     14k                      $ 11,165.00
#   Lab Grown     YG
#
# FIXED SLOTS: every attribute has its own reserved cell. When a piece lacks that datum
# the cell is left EMPTY and no other value shifts position. That was the flaw in the
# inherited tag -- unlabelled values with gaps, where whatever sat below "moved up" and the
# same line meant different things on different pieces.
#
# Weight and quantity share one cell ("0.62ct x41"), which is how they get read anyway:
# with 72 usable dots there is room for 4 rows of 18, not 5.
GRID = [["carat_qty", "clasp"],
        ["clarity", "measure"],
        ["color", "karatage"],
        ["origin", "metal"]]
# THE SPEC BLOCK GREW from 14 to 17 in height (user request 2026-08-03: "make it more
# visible") WITHOUT the text taking up a single dot more in width. This works because of
# how ^A0N quantizes: the glyph width is set by the width parameter, not the height, and it
# comes in steps -- measured, widths 7, 8, 9 and 10 all render identically, and only at 11
# does the text grow. So height 17 with width 10 gives letters 21% taller at exactly the
# width they had. It is free: it does not touch the fold, nor force the columns to be
# reallocated.
#
# The row step goes from 18 to 20 to keep the air between lines. With that, the spec block
# occupies 25..102, which is exactly where the price ends: the two blocks close level with
# each other and leave 5 dots to the die-cut, the same margin given to the price.
TABLE_ROW_STEP = 20
FONT_TABLE = (17, 10)

# BOTH COLUMNS WERE SHIFTED LEFT (2026-08-03) so the second one ends BEFORE the fold. They
# used to sit at 10..96 and 98..210: the second was born on one side of the crease and died
# on the other, and "Box w/ Hidden Safety" already reached dot 183, right on top of the
# fold mark.
#
# The width of column 2 is set by the REAL worst case in the catalog, not by the sample:
# the longest clasp value is "Push Lock w/ Figure 8" = 88 dots, measured on the render
# rather than estimated. And it cannot be shrunk by condensing the font: widths 9, 8 and 7
# all give the same 88 dots -- the ^A0N width parameter bottoms out and stops condensing.
# So column 2 needs 88 dots no matter what, and that dictates where it has to start:
#     end = FOLD_DOTS - FOLD_CLEARANCE = 176   ->   start = 176 - 88 = 88
# That leaves column 1 with 76 dots (10..86). More than enough: its widest value measured
# across the catalog is 45 dots.
#
# What this does NOT solve: unabbreviated metals ("Black & Carnation & Grey & Yellow", 139
# dots) still do not fit. They did not fit before either -- this is not a regression of
# this change, but it is recorded as a separate open item.
TABLE_COLS_X = [0, 78]                # col 1: the stone. col 2: measurement and alloy
TABLE_COL_W = [76, 88]

# The spec block drops 5 dots below the general margin (user request 2026-08-03). It gets
# a constant of its own rather than moving Y_TOP: Y_TOP also governs the SKU, so shifting
# it would drag the identity column down with it, and that column is already where it
# belongs.
TABLE_NUDGE = 5
TABLE_TOP = Y_TOP + TABLE_NUDGE       # 25

# Identity block: SKU, description and price STACKED, all three starting in the SAME
# column (Gabriel's request by voice note, 2026-07-31; the description used to sit in a
# column of its own, over the tail).
#
# Moved from 214 to 188 (2026-08-03) so it rests against the fold instead of leaving 32
# dots of dead space. That is what Gabriel circled in blue on the photo: his mark falls
# exactly in that gap (dots 184..212), not on the column.
COL_X = FOLD_DOTS + FOLD_CLEARANCE            # 188: against the fold, on the outer side

# The width is NOT capped at the 131 dots of paddle left on the right: it runs to the tag's
# real edge, crossing the paddle/tail seam on purpose. That is what lets a long description
# fit on ONE line without shrinking its font. ^PW710 already anchors the block to the left
# margin, so nothing else shifts.
COL_W = TAG_RIGHT_EDGE_DOTS - COL_X

# THE SKU DOES NOT USE THE SCALABLE FONT (2026-08-05). `A0` is the Zebra's only
# proportional, scalable font, and at this size it CONDENSES THE STROKE: the digits clog up
# and read as if stacked on each other. This is what Gabriel has been flagging since 04/08,
# and size does not fix it -- 18,13 / 22,13 / 22,15 and 24,13 were all tried and the defect
# persists. The scalable family has to be abandoned.
#
# Three physical demos were printed with the same SKU and Armen picked the first (font D,
# `^ADN,18,10`), asking for it 20% smaller. FONT D CANNOT BE MADE SMALLER: fixed-pitch
# bitmap fonts do not go below their base size -- `^ADN,14,8` returns a render IDENTICAL to
# `^ADN,18,10` (153x14 dots, measured in Labelary). The next step down within the family is
# B, and that is where it went on 2026-08-05.
#
# ON PAPER, B CAME OUT SMALL (2026-08-06). The strip the store sent carries both: the bottom
# two printed with the old scalable font and the top two with B. Measured on the photo
# against the height of the price, B yields 0.64 of that reference against the scalable
# font's 0.80 -- so escaping the clogging also cost body. The family was confirmed (B reads
# digit by digit where the scalable font ran the "526" together); what was missing was
# getting the size back.
#
# FONT D IS NO GOOD, EVEN THOUGH IT WAS THE ONE CHOSEN: it was tried (`^ADN,18,10`) and on
# paper a 15-character SKU ends at dot 364 with the paddle/tail step at 360 -- it touches
# the die-cut. And that is not a rare case: of 24,388 variants with a SKU in v19, **51.5%
# have 15 characters** and 43.6% have 13. The store's requirement is that the SKU touch the
# die-cut on no side, so D is ruled out on width, not on shape.
#
# THE WAY OUT: BITMAP FONTS SCALE HEIGHT AND WIDTH SEPARATELY. Measured in Labelary,
# `^ABN,22,7` is font B with the HEIGHT doubled and the width UNTOUCHED -- which is not the
# same as `^ABN,22,14`, that doubles both and eats into the tail. The multipliers are
# integers and each axis goes its own way; a value that is not a multiple is rounded down
# (`^ABN,16,7` draws exactly like `^ABN,11,7`).
#
#   font          ink height      width 16 char.  ends at dot
#   B 11,7             11              142              329
#   D 18,10            14              188              376   <- hits the step (360)
#   B 22,7             22              142              329   <- 31 dots of air
#
# In other words: taller than D with the width of B. The cost is proportion -- the glyphs
# come out stretched 2:1, tall and narrow. That is the price of always fitting.
FONT_SKU = (22, 7)
FONT_SKU_CMD = "ABN"

FONT_DESC = (14, 8)
FONT_PRICE = (24, 18)

# THE PRICE DROPS until it rests against the die-cut (Gabriel's request of 2026-08-01, the
# green mark on the photo). It no longer hangs off the canvas's Y_BOT but off the MEASURED
# paper, which is the limit that matters. Gabriel's green mark starts at dot 78 and this
# calculation lands exactly there -- mark and measurement agree on their own.
PRICE_SAFETY = 5         # air between the foot of the price and the die-cut

Y_SKU = Y_TOP + 2
Y_PRICE = PAPER_CUT_DOTS - PRICE_SAFETY - FONT_PRICE[0]      # 78

# THE DESCRIPTION HANGS OFF THE TAIL, NOT OFF THE GAP (2026-08-06). It used to be centred
# in the free space between the SKU and the price, which is a PADDLE criterion -- and the
# description is the one field that leaves the paddle and continues over the tail. With the
# tail's two die lines now measured (dots 49 and 68), the right centring is that window's:
# the part that falls outside the paddle then lands inside the box instead of riding over
# the cut.
#
# The previous version left the ink at 49..59, resting RIGHT ON the upper line: the photo
# of 06/08 shows the die-cut crossing the text end to end. Centred, it gives 53..63, with
# 4 dots of air on each side.
#
# The font size is not the ink height: `A0N,14,8` draws 11 dots and starts them ONE DOT
# ABOVE the ^FO (both measured in Labelary). What gets centred is the INK, which is what
# you see, and only then is it converted to an ^FO coordinate.
DESC_INK_H = 11
DESC_INK_OFFSET = -1

# DESC_NUDGE: the GEOMETRIC centre is not the one that reads as centred. With the window at
# 51..71 the calculation leaves the ink at 55..65, and on paper that reads high -- store
# request of 2026-08-06: "drop it 2 dots". It agrees with the measurement: the peaks of the
# two die lines came out at {50, 51, 53} and {70, 72, 73}, so the real window sits a couple
# of dots below the midpoint of those groups. Corrected with an offset rather than by
# hard-coding the value, so the automatic centring survives a change of font.
DESC_NUDGE = 2
Y_DESC = (COLA_TOP_DOTS + (COLA_BOT_DOTS - COLA_TOP_DOTS - DESC_INK_H) // 2
          - DESC_INK_OFFSET + DESC_NUDGE)


def _zpl_safe(text):
    """`^` and `~` are ZPL command prefixes: inside an ^FD they break the label."""
    return (text or "").replace("^", " ").replace("~", " ")


def _field(x, y, font, text, width, lines=1, align="L", cmd="A0N"):
    """Un campo de text.

    The width is resolved with ^FB, meaning THE PRINTER fits it using the font's real
    metrics and breaking on word boundaries. We do no trimming of our own: that arithmetic
    - an estimated width per character - is exactly what used to cut the spec block off
    mid-word -- "Box w/ Hi", "18k Black Rhodi".

    `cmd` is the font. It defaults to the scalable `A0N`, used by the spec block, the
    description and the price. Only the SKU passes something else (see FONT_SKU_CMD): the
    scalable font clogs its digits.
    """
    if not text:
        return ""
    return "^FO%d,%d^%s,%d,%d^FB%d,%d,1,%s^FD%s^FS" % (
        x, y, cmd, font[0], font[1], width, lines, align, _zpl_safe(text))


class ProductProduct(models.Model):
    _inherit = "product.product"

    # --- THE TAG'S VALUES, ON SCREEN ----------------------------------------
    # The eight cells of the spec block, exposed as fields so the store can read on the
    # form what is going to come out on paper without having to print a tag to find out.
    #
    # They are computed FROM `_get_label_cells()`, never from a second copy of the rules:
    # the abbreviated metal, the stone family that won the priority list, the first
    # measurement in the cascade. One source, so the tab cannot drift away from the tag.
    #
    # NOT STORED: they are a projection of attributes that already live in the database.
    # Storing them would mean keeping them in step with every attribute edit for no gain,
    # since they are only ever read one record at a time, on this form.
    label_carat_qty = fields.Char("Carat / Qty", compute="_compute_label_cells")
    label_clarity = fields.Char("Clarity", compute="_compute_label_cells")
    label_color = fields.Char("Color", compute="_compute_label_cells")
    label_origin = fields.Char("Origin", compute="_compute_label_cells")
    label_clasp = fields.Char("Clasp", compute="_compute_label_cells")
    label_measure = fields.Char("Measure", compute="_compute_label_cells")
    label_karatage = fields.Char("Karatage", compute="_compute_label_cells")
    label_metal = fields.Char("Metal", compute="_compute_label_cells")
    # The printed tag carries no captions -- only values at fixed spots -- so a family
    # that reuses a cell prints correctly. This screen DOES caption them, and would read
    # "Clarity: Stainless Steel" on a watch. This line says what each reused cell is
    # actually showing, so nobody has to guess.
    label_slots_note = fields.Char(compute="_compute_label_cells")

    def _get_attribute_map(self):
        """The piece's attributes, combining template and variant.

        The gemological data (carat, clarity, color, origin, shape) is configured as
        `no_variant`: Odoo leaves it on the template's line and NEVER hangs it off
        `product_template_attribute_value_ids`. Reading the variant alone returned a tag
        with no stone spec at all.

        Only single-valued lines are taken from the template: when a line holds several
        values (Material = White/Rose/Yellow Gold, say) it is a variant-generating
        attribute, and the value for this particular piece comes from the variant.
        """
        self.ensure_one()
        vals = {}
        for line in self.product_tmpl_id.attribute_line_ids:
            if len(line.value_ids) == 1:
                vals[line.attribute_id.name] = line.value_ids.name
        # The variant wins: it overrides the template wherever it has a value of its own.
        for ptav in self.product_template_attribute_value_ids:
            vals[ptav.attribute_id.name] = ptav.name
        return vals

    def _get_family_slots(self):
        """The cell mapping this piece's family uses, or None to keep the jewellery one.

        FIRST the configuration on the product category (`yag.tag.line`), which is where
        this belongs: it can be changed by whoever knows the pieces, without a deploy, and
        it inherits along the category tree so a branch is set up once. A cell may hold
        several attributes -- they are tried in the order they were dragged into, the way
        the tag has always worked.

        The hardcoded map below is the FALLBACK, kept so nothing that works today can
        break while the branches are being configured. Once every family has its setup it
        can go.
        """
        self.ensure_one()
        _origen, config = self.categ_id._yag_tag_config()
        if config:
            slots = {}
            for line in config.sorted("sequence").filtered("slot"):
                slots.setdefault(line.slot, []).append(line.attribute_id.name)
            if slots:
                return slots
        path = self.categ_id.complete_name or ""
        for token, family in FAMILY_BY_CATEGORY.items():
            if token in path:
                return FAMILY_SLOTS.get(family)
        return None

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
        """The first attribute in the cascade that carries a value."""
        for name in candidates:
            if attr_map.get(name):
                return attr_map[name]
        return ""

    def _get_label_cells(self):
        """The spec values BROKEN OUT, one per table cell.

        The fixed-slot layout needs every datum separately so it can be given its reserved
        position; the running line of the previous layout (stone | alloy | measurement, all
        concatenated) was no use for that.
        """
        self.ensure_one()
        attr_map = self._get_attribute_map()
        specs = self._get_stone_specs(attr_map)

        # `Case Material` is the watch's way of saying Material. Same cause as
        # `Case Diameter` above: the slot exists, the attribute is loaded, and the tag
        # simply was not looking for that name.
        metal = (attr_map.get("Material") or attr_map.get("Case Material")
                 or attr_map.get("Primary Color", ""))
        carat = specs.get("carat", "")
        quantity = specs.get("quantity", "")
        cells = {
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
        # The family, if it has its own slots, redefines what some cells hold. It is
        # applied LAST and only where it finds a value, so a piece that does carry the
        # jewellery datum keeps it: the family adds, it never blanks a cell that had
        # something in it.
        for cell, candidates in (self._get_family_slots() or {}).items():
            value = self._first_of(attr_map, candidates)
            if value:
                cells[cell] = value
        return cells

    @api.depends("product_template_attribute_value_ids",
                 "product_tmpl_id.attribute_line_ids.value_ids",
                 "categ_id", "categ_id.yag_tag_line_ids")
    def _compute_label_cells(self):
        """Each cell to its own field, straight off the same dictionary the tag is built
        from. An empty cell stays empty here too -- that is the fixed-slot rule of the
        layout, and hiding it on screen would misrepresent the tag."""
        for record in self:
            cells = record._get_label_cells()
            record.label_carat_qty = cells["carat_qty"]
            record.label_clarity = cells["clarity"]
            record.label_color = cells["color"]
            record.label_origin = cells["origin"]
            record.label_clasp = cells["clasp"]
            record.label_measure = cells["measure"]
            record.label_karatage = cells["karatage"]
            record.label_metal = cells["metal"]
            slots = record._get_family_slots()
            record.label_slots_note = (
                "On this family the cells are reused: "
                + ", ".join("%s shows %s" % (CELL_CAPTION.get(c, c), " / ".join(v))
                            for c, v in slots.items())
                if slots else False)

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

    # --- CHATTER PREVIEW ----------------------------------------------------
# Every print is recorded in the variant's chatter with the tag drawn OVER THE DIE-CUT.
# Without the die-cut drawn in, the image misleads: the raw ZPL render shows a 112-dot
# canvas that does not exist on paper, says nothing about where the cut falls or where the
# tag folds - and those are precisely the two limits a layout is validated against.

    LABELARY_URL = "http://api.labelary.com/v1/printers/8dpmm/labels/3.5x0.55/0/"
    PREVIEW_SCALE = 4          # 1 px per dot is unreadable on screen; 4x gives 2840x508
    PREVIEW_LEGEND_H = 108     # bottom band for the legend

    def _legend_font(self):
        """PIL's default font is 11px and is unreadable on a 2840-wide canvas. DejaVu is
        used instead - it ships in the Odoo.sh image, verified - with a fallback in case it
        is gone tomorrow: the preview must not fall over because of a typeface."""
        from PIL import ImageFont
        for ruta in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"):
            try:
                return ImageFont.truetype(ruta, 26)
            except OSError:
                continue
        return ImageFont.load_default()

    def _labelary_png(self, zpl):
        """Rasterize the ZPL with Labelary: it is a real ZPL interpreter, so the PNG is
        what the Zebra will put out rather than an approximation of ours. Returns None when
        the service does not answer -- recording the print does not depend on the image."""
        try:
            r = requests.post(self.LABELARY_URL, data=zpl.encode("utf8"), timeout=10)
            r.raise_for_status()
            return r.content
        except Exception as e:
            _logger.warning("Labelary could not rasterize the tag: %s", e)
            return None

    def _draw_die_cut(self, png_bytes):
        """Paste the render onto the REAL paper and draw the die-cut over it.

        The render comes with the ZPL canvas (y=0..111). The paper does not line up:
        it starts at dot -20 (that strip exists but the printhead cannot reach it) and
        the cut falls at +107. So the render is clipped at 107 and pasted 20 dots
        lower, which makes the image's coordinates those of the PAPER, not of the
        canvas.

        Colour-blind-safe coding (blue/orange, never green/red): BLUE for the die-cut
        edge and the tail seam, ORANGE for the fold -- the one limit that splits text
        across two faces, and the one worth making obvious.
        """
        render = Image.open(io.BytesIO(png_bytes)).convert("L")
        paper_h = PAPER_CUT_DOTS - PAPER_TOP_DOTS          # 127
        offset = -PAPER_TOP_DOTS                             # 20

        paper = Image.new("L", (CANVAS_WIDTH_DOTS, paper_h), 255)
        paper.paste(render.crop((0, 0, CANVAS_WIDTH_DOTS,
                                 min(PAPER_CUT_DOTS, render.height))), (0, offset))

        s = self.PREVIEW_SCALE
            # NEAREST, not bicubic: every dot has to look like the square it is.
            # Smoothing the scale invents greys and makes text look legible that on
            # paper is not.
        out = paper.resize((CANVAS_WIDTH_DOTS * s, paper_h * s),
                           Image.NEAREST).convert("RGB")
        canvas = Image.new("RGB", (out.width, out.height + self.PREVIEW_LEGEND_H), "white")
        canvas.paste(out, (0, 0))
        d = ImageDraw.Draw(canvas)

        BLUE, ORANGE, GREY = (0, 82, 155), (214, 106, 0), (150, 150, 150)

            # The top strip the printhead cannot reach, hatched so it is not mistaken
            # for usable paper. It is where the store's "it prints too high" came from.
        for x in range(0, canvas.width, 12):
            d.line([(x, 0), (x + offset * s, offset * s)], fill=GREY, width=1)
        d.line([(0, offset * s), (canvas.width, offset * s)], fill=GREY, width=2)

        d.rectangle([(0, 0), (out.width - 1, out.height - 1)], outline=BLUE, width=3)

        for x_dot, color, width in ((FOLD_DOTS, ORANGE, 3),
                                    (CONTENT_WIDTH_DOTS, BLUE, 2)):
            x = x_dot * s
            for y in range(0, out.height, 16):     # dashed, so it does not hide what is underneath
                d.line([(x, y), (x, y + 8)], fill=color, width=width)

        font = self._legend_font()
        base = out.height + 10
        for i, (text, color) in enumerate((
            ("BLUE: die-cut edge (cut at dot %d) and hang-tail seam (dot %d, which rolls "
             "up and stays hidden)"
             % (PAPER_CUT_DOTS, CONTENT_WIDTH_DOTS), BLUE),
            ("ORANGE: fold line (dot %d) -- anything crossing it is split between the "
             "two faces of the tag" % FOLD_DOTS, ORANGE),
            ("HATCHED: the %d dots of paper the printhead cannot reach (they start "
             "above y=0)" % offset, GREY),
        )):
            d.text((10, base + i * 32), text, fill=color, font=font)

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()

    def _label_preview_attachment(self, zpl):
        """The preview attachment, cached by the ZPL hash: as long as the tag does not
        change the render is not requested again, even if it is printed ten times."""
        self.ensure_one()
        digest = hashlib.sha256(zpl.encode("utf8")).hexdigest()[:12]
        fname = "tag_%s_%s.png" % (self.default_code or self.id, digest)
        Att = self.env["ir.attachment"]
        att = Att.search([("res_model", "=", "product.product"),
                          ("res_id", "=", self.id), ("name", "=", fname)], limit=1)
        if att:
            return att
        raw = self._labelary_png(zpl)
        if not raw:
            return Att
        return Att.create({
            "name": fname,
            "res_model": "product.product",
            "res_id": self.id,
            "mimetype": "image/png",
            "datas": base64.b64encode(self._draw_die_cut(raw)),
        })

    def action_log_printed_label(self):
        """Called by the button AFTER the bridge has confirmed the print. What gets posted
        is what actually came out on paper; failed attempts do not clutter the chatter."""
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
