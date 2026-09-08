# -*- coding: utf-8 -*-
"""The tags of a whole receipt, printed from the receipt.

Why here
--------
This is where the three things happen at once: the goods arrive, the serial numbers are
typed in, and the pieces need a tag before they reach the case. Sending someone to open
each piece afterwards is asking them to walk the same list twice, and the second walk is
the one that does not happen.

Measured on v19's receipts: the median one has 2 lines and 96% of the lines are a single
unit, so "one tag per unit received" is the actual size of the job -- not a batch job.

How the printer takes them
--------------------------
A Zebra reads a stream of labels, one ^XA...^XZ after another, so the whole receipt
travels in the SAME send the single tag uses. Nothing new is needed at the bridge.

What it does NOT do
-------------------
It does not decide anything about a piece. A line with a serial prints its serial; a line
without one prints the tag as it has always printed. Whether a family gets serialised is a
separate decision, and this button does not force it.
"""
from markupsafe import Markup

from odoo import _, models

# Renders posted to the chatter, at most: past this, the entry lists the lines instead.
# Each render is a round trip to the rasterizer, and a receipt of 49 lines would hang the
# button on a wall of pictures nobody looks at one by one.
MAX_PREVIEWS = 4


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _label_lines(self):
        """One entry per TAG to print: (variant, serial, how many).

        Reads the operation lines, which is where the serial actually lands when the goods
        are received -- the move above them knows the model, not the piece.
        """
        self.ensure_one()
        salida = []
        for ml in self.move_line_ids:
            unidades = int(ml.quantity or 0)
            if unidades <= 0 or not ml.product_id:
                continue
            salida.append((ml.product_id, ml.lot_id.name or None, unidades))
        return salida

    def get_jewelry_label_zpl(self):
        self.ensure_one()
        etiquetas = []
        for producto, serial, unidades in self._label_lines():
            zpl = producto.get_jewelry_label_zpl(serial=serial)
            etiquetas.extend([zpl] * unidades)
        return "".join(etiquetas)

    def action_log_printed_label(self, impreso=True):
        """The record goes on the RECEIPT: what was printed is this list, in one go."""
        self.ensure_one()
        lineas = self._label_lines()
        total = sum(u for _p, _s, u in lineas)
        cuerpo = ["<p><strong>%s</strong> &mdash; %s</p>" % (
            _("Tags printed") if impreso else _("Tags previewed"), self.display_name)]
        if not impreso:
            cuerpo.append("<p>%s</p>" % _(
                "They did NOT come out of the printer: the bridge did not answer. This is "
                "what would have been printed."))
        cuerpo.append("<p>%s</p>" % _("%s tags, one per unit received:", total))
        filas = []
        for producto, serial, unidades in lineas:
            filas.append("<li>%s%s%s</li>" % (
                producto.default_code or producto.display_name,
                _(" &mdash; serial %s", serial) if serial else "",
                (" &times; %s" % unidades) if unidades > 1 else ""))
        cuerpo.append("<ul>%s</ul>" % "".join(filas))

        adjuntos = self.env["ir.attachment"]
        if len(lineas) <= MAX_PREVIEWS:
            for producto, serial, _u in lineas:
                adjuntos |= producto._label_preview_attachment(
                    producto.get_jewelry_label_zpl(serial=serial), destino=self)
        self.message_post(
            body=Markup("".join(cuerpo)),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
            attachment_ids=adjuntos.ids,
        )
        return True
