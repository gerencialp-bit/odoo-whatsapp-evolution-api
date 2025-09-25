# -*- coding: utf-8 -*-
{
    'name': "WhatsApp Contact Management",
    'version': '18.0.1.0.3',
    'summary': 'Manages privacy and separation of WhatsApp contacts.',
    'description': "...",
    'author': "Odoo Evolution Architect",
    'category': 'Sales/CRM',
    'depends': [
        'whatsapp_evolution_base',
        'contacts',
        'mail',
        'phone_validation',
        'whatsapp_evolution_ui_utils',  # <-- Dependência Adicionada
    ],
    'data': [
        'security/model_access.xml',
        'security/ir.model.access.csv',
        'security/contact_security.xml',
        'data/whatsapp_contact_config_data.xml',
        'views/whatsapp_contact_config_views.xml',
        'views/res_partner_views_muk_inspired.xml', # <-- NOVO ARQUIVO DE VIEW
        'views/contact_views.xml',
        'views/res_partner_views_inherit.xml',
        'views/contact_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}