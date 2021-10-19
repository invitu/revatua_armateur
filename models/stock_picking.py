# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class Picking(models.Model):
    _inherit = 'stock.picking'

    total_product_uom_qty = fields.Float("Quantity", compute='_compute_shipping_qty',
                                         help="Total quantity of product for Shipping")

    @api.depends('move_line_ids', 'move_line_ids.product_uom_qty', 'move_line_ids.qty_done')
    def _compute_shipping_qty(self):
        for picking in self:
            total_qty = 0.0
            for move_line in picking.move_line_ids:
                if move_line.product_id and not move_line.result_package_id:
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
                    depart_date = max([i.date_depart for i in depart_trajets_ids if i.date_depart <= arrival_date])
                    if (depart_date):
                        if picking.picking_type_id.code == 'internal':
                            picking.scheduled_date = depart_date
                        elif picking.picking_type_id.code == 'outgoing':
                            picking.scheduled_date = arrival_date
                        break
