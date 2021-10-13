# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    port_tax_minimum_value = fields.Float(
        string="Valeur minimale d'application de la taxe portuaire",
        related='company_id.port_tax_minimum_value',
        help='Set minimum value for connaissement to get a port tax',
        readonly=False
    )