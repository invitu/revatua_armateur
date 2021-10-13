# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ResCompany(models.Model):
    _inherit = 'res.company'

    revatua_certif_pwd = fields.Char(
        string='Password certificate',
        help="Enter your certificate password (given by DPAM)"
    )
    port_tax_minimum_value = fields.Float()

    def write(self, values):
        # Check if minimum fret price is higher than minimum port tax
        if (values.get('port_tax_minimum_value')):
            port_tax_minimum_value = values.get('port_tax_minimum_value')
            minimum_fret_price = float(self.env['ir.config_parameter'].sudo()
                                       .get_param('revatua_armateur.minimum_fret_price'))
            if (port_tax_minimum_value < minimum_fret_price):
                raise UserError(
                    _('Attention, le prix minimal de la taxe portuaire doit être supérieur ou égal au prix minimal de fret:\n\n%s') % (minimum_fret_price))
        return super(ResCompany, self).write(values)
