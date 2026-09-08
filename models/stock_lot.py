# -*- coding: utf-8 -*-
"""The tag, printed from the PIECE.

Why the piece
-------------
A serial number belongs to the piece, not to the model: two identical rings share one
product and carry a number each. The tag is what tells them apart on the counter, so it
has to be printable from the record that holds the number -- and that record is the lot.

This is also the more operative of the two doors. The serial and the GIA certificate are
typed in when the goods are received, on this very screen, so the tag can be printed in
the same movement instead of hunting for the model afterwards.

No drawing of its own
---------------------
Both methods hand off to the variant, passing the serial. There is ONE geometry and one
chatter format for the whole module; what changes here is only where the number comes from
and where the record of the print is kept -- on the piece, which is what was printed.

The method names are the variant's on purpose: the button widget reads the model off the
record it sits on, so the same button works on both screens with no branch in the browser.
"""
from odoo import _, models
from odoo.exceptions import UserError


class StockLot(models.Model):
    _inherit = "stock.lot"

    def get_jewelry_label_zpl(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_("This serial number has no product, so there is no tag to "
                              "print: the tag reads the model's SKU, description and "
                              "price."))
        return self.product_id.get_jewelry_label_zpl(serial=self.name)

    def action_log_printed_label(self, impreso=True):
        self.ensure_one()
        return self.product_id._post_label_to(
            self, self.get_jewelry_label_zpl(), impreso=impreso)
