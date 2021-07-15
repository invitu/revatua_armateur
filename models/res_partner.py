# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    property_product_pricelist = fields.Many2one(
        domain=lambda self: [('type', '=', 'standard')],
    )
    property_product_pricelist_fret = fields.Many2one(
        'product.pricelist', 'Fret Pricelist',
        domain=lambda self: [('type', '=', 'fret')],
        inverse="_inverse_product_pricelist", company_dependent=False,
        help="This Fret pricelist will be used, instead of the default one, for sales to the current partner")
