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
        'revatua_connector',
        'sale_order_type',
    ],

    # always loaded
    'data': [
        #'security/revatua_security.xml',
        #'security/ir.model.access.csv',
        'data/sale_order_type_data.xml',
        'data/product.category.csv',
        'views/sale_order_views.xml',
        'views/product_template_views.xml',
        'views/product_pricelist_views.xml',
        'views/product_views.xml',
        #'views/revatua_menu_views.xml',
        #'views/voyage_views.xml',
        #'views/res_company_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
    'installable': True,
}
