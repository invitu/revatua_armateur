# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import timedelta


class DuplicateVoyages(models.TransientModel):
    _name = "duplicate.voyages"
    _description = "Duplicate voyages"

    deltadays = fields.Integer(
        string='Days for duplicate',
        help='Enter the number of days you want to duplicate the voyages to')

    def duplicate_voyages(self):
        voyages = self.env['voyage'].browse(self._context.get('active_ids', []))
        if self.deltadays <= 0 or self.deltadays > 91:
            raise UserError(_("You cannot duplicate voyages to less than 1 day or more than 91 days."))
        for voyage in voyages:
            new_voyage = voyage.copy()
            new_voyage.date_arrivee = new_voyage.date_arrivee and new_voyage.date_arrivee + timedelta(days=self.deltadays) or ''
            new_voyage.date_depart = new_voyage.date_depart and new_voyage.date_depart + timedelta(days=self.deltadays) or ''
            for trajet in new_voyage.trajet_ids:
                trajet.date_arrivee = trajet.date_arrivee + timedelta(days=self.deltadays)
                trajet.date_depart = trajet.date_depart + timedelta(days=self.deltadays)

        return {'type': 'ir.actions.act_window_close'}
