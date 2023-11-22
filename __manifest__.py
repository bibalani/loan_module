# -*- coding: utf-8 -*-
{
    'name': "loan",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "NAK",
    'website': "http://www.nak-mci.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/12.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'ext_hr_employee','mail'],

    # always loaded
    'data': [
        'security/loan_security.xml',
        'security/ir.model.access.csv',
        'views/loan_views.xml',
        'views/loan_type_views.xml',
        'views/configuration_views.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}