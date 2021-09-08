# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    revatua_certif_pwd = fields.Char(string='Password certificate', help="Enter your certificate password (given by DPAM)")
