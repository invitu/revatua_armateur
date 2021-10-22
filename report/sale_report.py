# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models


class SaleFretReport(models.Model):
    _name = "sale.fret.report"
    _description = "Sales Fret Analysis Report"
    _auto = False
    _order = 'date desc'

    name = fields.Char('Order Reference', readonly=True)
    date = fields.Datetime('Order Date', readonly=True)
    product_id = fields.Many2one(
        'product.product', 'Product Variant', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    user_id = fields.Many2one('res.users', 'Salesperson', readonly=True)
    price_total = fields.Float('Total', readonly=True)
    price_subtotal = fields.Float('Untaxed Total', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Customer', readonly=True)
    partner_shipping_id = fields.Many2one(
        'res.partner', 'Shipping Customer', readonly=True)
    partner_invoice_id = fields.Many2one(
        'res.partner', 'Delivered Customer', readonly=True)
    product_tmpl_id = fields.Many2one(
        'product.template', 'Product', readonly=True)
    categ_id = fields.Many2one(
        'product.category', 'Product Category', readonly=True)
    pricelist_id = fields.Many2one(
        'product.pricelist', 'Pricelist', readonly=True)
    state_id = fields.Many2one(
        'res.country.state', 'Customer State', readonly=True)
    volume = fields.Float('Volume (m3)', readonly=True)
    poids = fields.Float('Poids (kg)', readonly=True)
    voyage_id = fields.Many2one('voyage', readonly=True)
    date_voyage = fields.Datetime('Date de depart', readonly=True)
    iledepart_id = fields.Many2one('res.country.state',
                                   'Ile de départ',
                                   readonly=True)
    ilearrivee_id = fields.Many2one('res.country.state',
                                    'Ile d\'arrivée',
                                    readonly=True)
    state = fields.Selection([
        ('draft', 'Draft Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Sales Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)

    order_id = fields.Many2one('sale.order', 'Order #', readonly=True)

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        with_ = ("WITH %s" % with_clause) if with_clause else ""

        select_ = """
            coalesce(min(l.id), -s.id) as id,
            l.product_id as product_id,
            CASE WHEN l.product_id IS NOT NULL THEN sum(l.price_total / CASE COALESCE(s.currency_rate, 0) WHEN 0 THEN 1.0 ELSE s.currency_rate END) ELSE 0 END as price_total,
            CASE WHEN l.product_id IS NOT NULL THEN sum(l.price_subtotal / CASE COALESCE(s.currency_rate, 0) WHEN 0 THEN 1.0 ELSE s.currency_rate END) ELSE 0 END as price_subtotal,
            count(*) as nbr,
            s.revatua_code as name,
            s.date_order as date,
            s.partner_id as partner_id,
            s.user_id as user_id,
            s.company_id as company_id,
            s.partner_shipping_id as partner_shipping_id,
            s.pricelist_id as pricelist_id,
            s.partner_invoice_id as partner_invoice_id,
            s.state as state,
            s.voyage_id as voyage_id,
            s.iledepart_id as iledepart_id,
            s.ilearrivee_id as ilearrivee_id,
            v.date_depart as date_voyage,
            t.categ_id as categ_id,
            p.product_tmpl_id,
            partner.state_id as state_id,
            CASE WHEN l.product_id IS NOT NULL THEN l.poids ELSE 0 END as poids,
            CASE WHEN l.product_id IS NOT NULL THEN l.volume ELSE 0 END as volume,
            s.id as order_id
        """

        for field in fields.values():
            select_ += field

        from_ = """
            sale_order_line l
                right outer join sale_order s on (s.id = l.order_id)
                join res_partner partner on s.partner_id = partner.id
                left join product_product p on (l.product_id = p.id)
                left join product_template t on (p.product_tmpl_id = t.id)
                left join product_pricelist pp on (s.pricelist_id = pp.id)
                left join voyage v on (s.voyage_id = v.id)
            %s
        """ % from_clause

        groupby_ = """
            l.product_id,
            l.order_id,
            l.poids,
            l.volume,
            t.categ_id,
            s.name,
            s.date_order,
            s.partner_id,
            s.user_id,
            s.partner_shipping_id,
            s.partner_invoice_id,
            s.state,
            s.company_id,
            s.campaign_id,
            s.medium_id,
            s.source_id,
            s.pricelist_id,
            s.analytic_account_id,
            s.iledepart_id,
            s.ilearrivee_id,
            s.voyage_id,
            p.product_tmpl_id,
            partner.state_id,
            v.date_depart,
            s.id %s
        """ % (groupby)

        return '%s (SELECT %s FROM %s GROUP BY %s)' % (with_, select_, from_, groupby_)

    def init(self):
        # self._table = sale_report
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (
            self._table, self._query()))
