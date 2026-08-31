# -*- coding: utf-8 -*-
"""What each family prints on its tag, configured on the product category.

Why the configuration lives here
--------------------------------
The eight cells were laid out for a ring with stones -- carat, clarity, colour, diamond
origin -- and the module decided what filled them with lists written in the code. That
worked while every piece was a jewel: a watch has none of those four, so the whole branch
printed them blank while the data a watch does carry had nowhere to go.

Measured over the 2,921 watch templates: with the jewellery lists only 3 watches print
four cells or more; reading the same attributes into cells that mean something for a
watch, 419 do. No data is loaded to get that.

The configuration hangs off `product.category` because the product already carries its
`categ_id`: the family is decided, nobody has to tag a piece by hand. And it inherits
along `parent_id`, so the branch is configured once -- 14 to 16 of them cover 99% of the
catalogue -- and its 146 leaves follow.

The line that does NOT belong here
----------------------------------
Whether a piece has versions is NOT a family decision, it is decided piece by piece when
loading: `Material` appears on 15,692 templates in the old system and opens variants on
744 of them, 4%. The same attribute, in the same category, sometimes describes and
sometimes offers a choice. So this model says WHAT IS PRINTED; how many values a given
product loads into a line stays with that product.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

# The eight cells of the tag, in the order they are read on the cardboard. They are the
# computed fields of `product.product`: the cardboard is die-cut, so there are eight and
# no more.
SLOTS = [
    ("carat_qty", "Carat / Qty"),
    ("clarity", "Clarity"),
    ("color", "Color"),
    ("origin", "Origin"),
    ("clasp", "Clasp"),
    ("measure", "Measure"),
    ("karatage", "Karatage"),
    ("metal", "Metal"),
]


class YagTagLine(models.Model):
    _name = "yag.tag.line"
    _description = "Tag configuration line for a product category"
    _order = "sequence, id"

    category_id = fields.Many2one(
        "product.category", required=True, ondelete="cascade", index=True)
    attribute_id = fields.Many2one("product.attribute", required=True)
    sequence = fields.Integer(default=10)
    slot = fields.Selection(
        SLOTS, string="Tag cell",
        help="Which of the eight cells this attribute prints in. Leave it empty for an "
             "attribute that should be loaded but not printed.")
    admite_varios = fields.Boolean(
        "Several values allowed", default=False,
        help="Whether a product of this family may carry more than one value here, which "
             "is what makes Odoo generate its versions.")
    obligatorio = fields.Boolean(
        "Required", default=False,
        help="Counts towards the family's completeness figure and warns when it is empty.")
    create_variant = fields.Selection(
        related="attribute_id.create_variant", readonly=True)

    _sql_constraints = [
        ("attr_por_categoria", "unique(category_id, attribute_id)",
         "That attribute is already configured on this category."),
    ]

    @api.constrains("category_id", "slot")
    def _check_slot_unico(self):
        """One attribute per cell. The tag has eight fixed spots and nothing moves up to
        fill a gap: two attributes on the same cell would silently hide one of them."""
        for line in self:
            if not line.slot:
                continue
            otra = self.search([("category_id", "=", line.category_id.id),
                                ("slot", "=", line.slot), ("id", "!=", line.id)], limit=1)
            if otra:
                raise ValidationError(
                    "The cell '%s' is already taken by '%s' on this category."
                    % (dict(SLOTS)[line.slot], otra.attribute_id.name))

    @api.constrains("admite_varios", "attribute_id")
    def _check_admite_varios(self):
        """The trap this constraint exists for: an attribute set to `no_variant` does NOT
        generate versions when it carries several values -- and on top of that it stops
        printing, because the tag reads single-valued lines from the template and the rest
        from the variant. It would be wrong both ways, with no error anywhere."""
        for line in self:
            if line.admite_varios and line.attribute_id.create_variant != "always":
                raise ValidationError(
                    "'%s' cannot take several values: it is set to '%s'. Only an "
                    "attribute that generates variants can, otherwise the versions are "
                    "never created and the attribute stops printing on the tag."
                    % (line.attribute_id.name, line.attribute_id.create_variant))


class ProductCategory(models.Model):
    _inherit = "product.category"

    yag_tag_line_ids = fields.One2many("yag.tag.line", "category_id", string="Tag setup")
    yag_tag_heredada_de = fields.Many2one(
        "product.category", compute="_compute_yag_tag", string="Setup inherited from",
        help="The branch this category takes its tag setup from.")
    yag_tag_lineas = fields.Integer(compute="_compute_yag_tag", string="Attributes printed")

    def _yag_tag_config(self):
        """The setup in force for this category: its own, or the nearest parent's.

        Walking up `parent_id` is what lets a branch be configured once. A leaf that
        really needs something different sets its own lines and stops inheriting.
        """
        self.ensure_one()
        nodo = self
        while nodo:
            if nodo.yag_tag_line_ids:
                return nodo, nodo.yag_tag_line_ids
            nodo = nodo.parent_id
        return self.browse(), self.env["yag.tag.line"]

    @api.depends("yag_tag_line_ids", "parent_id")
    def _compute_yag_tag(self):
        for cat in self:
            origen, lineas = cat._yag_tag_config()
            cat.yag_tag_heredada_de = origen if origen != cat else False
            cat.yag_tag_lineas = len(lineas.filtered("slot"))
