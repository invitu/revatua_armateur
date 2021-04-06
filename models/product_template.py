# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    est_contenant = fields.Boolean(string='Est un contenant',
                                   help='Cochez cette case si cet article est un contenant')
    weight_uom = fields.Many2one(comodel_name='uom.uom',
                                 string='Unité de mesure de poids',
                                 help='Unité de mesure de poids',
                                 domain="[('category_id', '=', 'Weight')]")
    volume_uom = fields.Many2one(comodel_name='uom.uom',
                                 string='Unité de mesure de volume',
                                 help='Unité de mesure de volume',
                                 domain="[('category_id', '=', 'Volume')]")
    prix_volume = fields.Integer(string='Prix au volume', help='Prix au volume')
