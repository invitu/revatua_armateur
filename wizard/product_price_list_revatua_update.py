# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from datetime import datetime
import pytz


class WizardPriceilistGetRevatua(models.TransientModel):
    _name = 'wizard.pricelist.get.revatua'
    _description = 'Wizard that gets the pricelist from revatua and compute it'

    date = fields.Date(string='Date', help='Enter the date of the validity')

    def get_tarif(self):
        timezone = pytz.timezone(self._context.get('tz') or self.env.user.tz or 'UTC')
        date = datetime.strftime(self.date, '%Y-%m-%d')
        url = 'tarifs/actif?dateTarif='+date+'&detailTarif=true'

        tarif_response = self.env['revatua.api'].api_get(url)
        version = tarif_response.json()["version"]
        idrevatua = tarif_response.json()["id"]
        datetarif = timezone.localize(datetime.strptime(tarif_response.json()["dateApplication"], '%Y-%m-%d')).astimezone(pytz.timezone('UTC')).strftime("%Y-%m-%d %H:%M")
        tarifmini = tarif_response.json()["tarifMinimum"]
        detailtarif = tarif_response.json()["detailTarifs"]
        print(version)
        print(idrevatua)
        print(datetarif)
        print(tarifmini)
        print(detailtarif)
        #on récupère la pricelist
        pricelists = self.env['product.pricelist'].browse(self._context.get('active_ids', []))
        for dic in detailtarif:
            codetarif = dic['codeTarif']
            categ_revatua = self.env['product.category'].search(
                [('code_revatua', '=', codetarif)])

            ile1 = self.env['res.country.state'].search(
                [
                    ('name', '=', dic['nomIleDepart']),
                    ('country_id', '=', self.env.ref('base.pf').id),
                ])
            ile2 = self.env['res.country.state'].search(
                [
                    ('name', '=', dic['nomIleArrivee']),
                    ('country_id', '=', self.env.ref('base.pf').id),
                ])
            if codetarif in ('GAZCUBI', 'GAZOLE', 'GAZCAMION', 'HYDROCITERNE', 'FRIGO', 'FRIGODGAE'):
                coef = 1000.0
            elif codetarif in ('FUTVIDE', 'ESPFT'):
                coef = 1000.0 / 200.0
            elif codetarif in ('ESPTQ'):
                coef = 1000.0 / 20.0
            else:
                coef = 1.0
            montant = coef * dic['montant']
            print(categ_revatua)
            print(ile1)
            print(ile2)
            print(montant)
            # Now we add tarif lines in pricelist
            # on ajoute les items
            if categ_revatua:
                for pricelist in pricelists:
                    pricelist.write({
                        'item_ids': [(0, 0, {
                            'ile1_id': ile1.id,
                            'ile2_id': ile2.id,
                            'applied_on': '2_product_category',
                            'categ_id': categ_revatua.id,
                            'compute_price': 'fixed',
                            'fixed_price': montant,
                            'date_start': datetarif,
                            'official_price': True,
                        })]
                    })
            else:
                raise UserError(_('Category %s does not exist') % codetarif)
