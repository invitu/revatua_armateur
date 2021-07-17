# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Revatua Armateur",

    'summary': '',
    'description': """
Ce module permet de gérer les ventes de fret, en connection avec Revatua
""",
    'author': 'EASYPME, Luce PASQUINI, Cyril Vinh Tung ',
    'website': 'http://www.easypme.com',

    'category': 'Module',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'l10n_pf_check_vat_ispf',
        'l10n_pf_customs_nomenclature',
        'revatua_connector',
        'sale_order_type',
        'web_domain_field',
    ],

    # always loaded
    'data': [
        #'security/revatua_security.xml',
        'security/ir.model.access.csv',
        'data/fret_minimum.xml',
        'data/product_category_data.xml',
        'data/product_data.xml',
        'data/cron.xml',
        'data/sale_order_type_data.xml',
        'data/mail_data.xml',
        'views/voyage_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'wizard/product_price_list_revatua_update_view.xml',
        'wizard/duplicate_voyages_views.xml',
        'wizard/dgae_invoices_wizard_view.xml',
        'views/product_pricelist_views.xml',
        'views/product_views.xml',
        'report/reports.xml',
        "report/layout.xml",
        'report/dgae_invoices.xml',
        #'views/revatua_menu_views.xml',
        #'views/voyage_views.xml',
        #'views/res_company_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
    'installable': True,
}
