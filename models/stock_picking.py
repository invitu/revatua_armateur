# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from itertools import groupby
from odoo.exceptions import UserError


class Picking(models.Model):
    _inherit = 'stock.picking'

    total_product_uom_qty = fields.Float("Quantity", compute='_compute_shipping_qty',
                                         help="Total quantity of product for Shipping")

    @api.depends('move_line_ids', 'move_line_ids.product_uom_qty', 'move_line_ids.qty_done')
    def _compute_shipping_qty(self):
        for picking in self:
            total_qty = 0.0
            for move_line in picking.move_lines:
                if move_line.product_id:
                    total_qty += move_line.product_uom_qty
            picking.total_product_uom_qty = total_qty

    def _compute_scheduled_date(self):
        super(Picking, self)._compute_scheduled_date()
        for picking in self:
            if picking.sale_id.type_id == self.env.ref('revatua_armateur.fret_sale_type'):
                trajets_ids = picking.sale_id.voyage_id.trajet_ids
                depart_trajets_ids = sorted(trajets_ids.filtered(
                    lambda trajet: trajet.ile_depart_id == picking.sale_id.iledepart_id), key=lambda x: x.date_depart)
                arrival_trajet_ids = sorted(trajets_ids.filtered(
                    lambda trajet: trajet.ile_arrivee_id == picking.sale_id.ilearrivee_id), key=lambda x: x.date_arrivee)
                for trajet in arrival_trajet_ids:
                    arrival_date = trajet.date_arrivee
                    depart_date = max(
                        [i.date_depart for i in depart_trajets_ids if i.date_depart <= arrival_date],
                        default=0
                    )
                    if (depart_date is not 0):
                        if picking.picking_type_id.code == 'internal':
                            picking.scheduled_date = depart_date
                        elif picking.picking_type_id.code == 'outgoing':
                            picking.scheduled_date = arrival_date
                        break

    def _confirm_picking_revatua(self):
        self.ensure_one()
        if (self.picking_type_id.code == 'internal' and self.sale_id.type_id == self.env.ref('revatua_armateur.fret_sale_type')):
            url = "connaissements/" + self.sale_id.id_revatua + "/changeretat"
            payload = {
                "evenementConnaissementEnum": "EMBARQUE",
                "nbColisPresent": self.total_product_uom_qty
            }
            self.env['revatua.api'].api_patch(url, payload)

    def _action_done(self):
        for picking in self:
            picking._confirm_picking_revatua()
        return super(Picking, self)._action_done()

    def button_validate(self):
        for picking in self:
            if (picking.picking_type_id.code == 'internal' and picking.sale_id.type_id == self.env.ref('revatua_armateur.fret_sale_type')):
                # Check if differences btw reserved & done
                if (any(picking.qty_done != 0 for picking in picking.move_line_ids)
                        and any(picking.product_uom_qty != picking.qty_done for picking in picking.move_line_ids)):
                    self._qty_error()
                # Group lines by product_id to compare their quantities
                grouped_picking = self._group_dict(picking.move_line_ids)
                grouped_sales = self._group_dict(picking.sale_id.order_line)
                if grouped_picking != grouped_sales:
                    self._qty_error()

        return super(Picking, self).button_validate()

    def _group_dict(self, element):
        grouped_element = {}
        sorted_element = sorted(element, key=lambda x: x.product_id.id)
        for k, g in groupby(sorted_element, key=lambda x: x.product_id):
            if k.is_fret and k.type in ('consu', 'product'):
                grouped_element[k] = sum(r['product_uom_qty'] for r in list(g))
        return grouped_element

    def _qty_error(self):
        raise UserError(
            _("Attention, il y a une différence de quantité des produits entre le connaissement et le bon de livraison."
              + "\nVeuillez régulariser cette différence pour continuer."))
