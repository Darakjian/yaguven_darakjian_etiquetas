# -*- coding: utf-8 -*-
"""Guided product creation: the category decides what is asked.

Why
---
Loading a product today means choosing among 189 attributes with nothing telling you
which eight matter for the piece in your hand. Measured on this catalogue: 81% of the
watches print one cell or none. The tag is where the shop meets the system, so the moment
to get the data right is when it is typed, not afterwards.

Here the category comes first and the form builds itself from its setup: the attributes
are given, the person only picks values, and the dropdown is already narrowed to that
attribute. Nobody has to know which eight matter.

No dynamic fields
-----------------
The wizard has ONE one2many. The onchange on `categ_id` fills it with a line per
configured attribute. Add an attribute to a category and the line shows up by itself, with
no code and no view to touch -- which is what makes the whole thing configurable by
whoever knows the pieces.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class YagProductWizard(models.TransientModel):
    _name = "yag.product.wizard"
    _description = "Guided product creation"

    name = fields.Char("Product name", required=True)
    categ_id = fields.Many2one("product.category", "Category", required=True)
    default_code = fields.Char("Internal reference")
    standard_price = fields.Float("Cost")
    list_price = fields.Float("Sales price")
    line_ids = fields.One2many("yag.product.wizard.line", "wizard_id", "Attributes")

    # Surfaced, never acted on by itself: whether this looks like a model already loaded.
    # Manual loading should SHOW the collision and let the person decide -- merging two
    # models silently is how a catalogue ends up wrong in a way nobody can trace.
    modelo_existente_id = fields.Many2one(
        "product.template", "Existing model", readonly=True)
    aviso = fields.Char(readonly=True)

    @api.onchange("categ_id")
    def _onchange_categ_id(self):
        """The category builds the form. This is the whole idea of the wizard."""
        self.line_ids = [(5, 0, 0)]
        if not self.categ_id:
            return
        _origen, config = self.categ_id._yag_tag_config()
        self.line_ids = [(0, 0, {
            "attribute_id": linea.attribute_id.id,
            "sequence": linea.sequence,
            "slot": linea.slot,
            "admite_varios": linea.admite_varios,
            "obligatorio": linea.obligatorio,
        }) for linea in config.sorted("sequence")]
        if not config:
            self.aviso = _("This category has no tag setup yet, so there is nothing to "
                           "ask for. Set it up on the category first.")
        else:
            self.aviso = False

    @api.onchange("name", "categ_id")
    def _onchange_name(self):
        """Look for a model that already exists before creating another one.

        Our loading scripts created one template per SKU and split models the shop keeps
        together -- the same watch in two dial colours ended up as two products. Manual
        loading would repeat it one piece at a time.
        """
        self.modelo_existente_id = False
        if not self.name or not self.categ_id:
            return
        tmpl = self.env["product.template"].search(
            [("name", "=ilike", self.name.strip()),
             ("categ_id", "=", self.categ_id.id)], limit=1)
        if tmpl:
            self.modelo_existente_id = tmpl
            self.aviso = _(
                "A model with this name already exists in this category with %s "
                "version(s). If this piece is another version of it -- another dial "
                "colour, another size -- add the value there instead of creating a "
                "second model."
            ) % tmpl.product_variant_count

    def action_crear(self):
        self.ensure_one()
        faltan = self.line_ids.filtered(lambda l: l.obligatorio and not l.value_ids)
        if faltan:
            raise UserError(_(
                "These attributes are required for this family and are empty: %s.\n\n"
                "They are what identifies the piece on the tag."
            ) % ", ".join(faltan.mapped("attribute_id.name")))
        cargadas = self.line_ids.filtered("value_ids")
        if not cargadas:
            raise UserError(_("No attribute carries a value: the tag would print empty."))

        tmpl = self.env["product.template"].create({
            "name": self.name.strip(),
            "categ_id": self.categ_id.id,
            "is_storable": True,
            "list_price": self.list_price,
            "standard_price": self.standard_price,
            "attribute_line_ids": [(0, 0, {
                "attribute_id": l.attribute_id.id,
                "value_ids": [(6, 0, l.value_ids.ids)],
            }) for l in cargadas],
        })
        variantes = tmpl.product_variant_ids
        if len(variantes) == 1 and self.default_code:
            variantes.default_code = self.default_code
        # More than one version means one code each, and they are filled in a list rather
        # than opening them one by one: with thirteen colours that is thirteen openings.
        return {
            "type": "ir.actions.act_window",
            "name": _("Codes for each version of %s") % tmpl.name,
            "res_model": "product.product",
            "view_mode": "list,form",
            "domain": [("id", "in", variantes.ids)],
            "context": {"create": False},
        }


class YagProductWizardLine(models.TransientModel):
    _name = "yag.product.wizard.line"
    _description = "Guided product creation line"
    _order = "sequence, id"

    wizard_id = fields.Many2one("yag.product.wizard", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    attribute_id = fields.Many2one("product.attribute", required=True, readonly=True)
    value_ids = fields.Many2many("product.attribute.value", string="Value")
    admite_varios = fields.Boolean(readonly=True)
    obligatorio = fields.Boolean(readonly=True)
    slot = fields.Char(readonly=True)

    @api.constrains("value_ids", "admite_varios")
    def _check_varios(self):
        """Several values are what makes Odoo generate the versions. Where the family did
        not allow it, one value: otherwise a piece that should be one turns into several,
        each with its own stock, and undoing that is not a one-liner."""
        for line in self:
            if len(line.value_ids) > 1 and not line.admite_varios:
                raise UserError(_(
                    "'%s' takes a single value on this family. Loading several would "
                    "create one version of the product per value."
                ) % line.attribute_id.name)
