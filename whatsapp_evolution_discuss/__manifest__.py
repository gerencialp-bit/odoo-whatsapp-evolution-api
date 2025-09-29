# -*- coding: utf-8 -*-
{
    'name': "WhatsApp Evolution - Discuss Integration",
    'version': '18.0.1.0.3', # Incrementando a versão
    'summary': 'Integrates WhatsApp Evolution with Odoo Discuss and Chatter.',
    'description': """
        - Enables two-way conversations via Odoo Discuss.
        - Adds a 'Send WhatsApp' button to the chatter.
        - Creates dedicated WhatsApp channels for contacts.
    """,
    'author': "Odoo Evolution Architect",
    'category': 'Discuss',
    'depends': [
        'whatsapp_evolution_base',
        'whatsapp_contact_management',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/whatsapp_composer_views.xml',
        # 'data/automation.xml', # <-- LINHA REMOVIDA
    ],
    'assets': {
        'web.assets_backend': [
            # Patches existentes
            'whatsapp_evolution_discuss/static/src/js/chatter_patch.js',
            'whatsapp_evolution_discuss/static/src/xml/chatter.xml',
            # Novos patches para o Discuss
            'whatsapp_evolution_discuss/static/src/core/common/thread_model_patch.js',
            'whatsapp_evolution_discuss/static/src/core/public_web/discuss_app_model_patch.js',
            'whatsapp_evolution_discuss/static/src/core/web/channel_selector_patch.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}