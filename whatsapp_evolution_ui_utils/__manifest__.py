# -*- coding: utf-8 -*-
{
    'name': "WhatsApp Evolution - UI Utils",
    'version': '18.0.1.0.0',
    'summary': 'Provides UI widgets and visual improvements for Evolution modules.',
    'description': "Technical module inspired by muk_web_utils, providing custom widgets like selection_icons and text_icon.",
    'author': "Odoo Evolution Architect",
    'category': 'Technical',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'whatsapp_evolution_ui_utils/static/src/js/selection_icons_widget.js',
            'whatsapp_evolution_ui_utils/static/src/xml/selection_icons_widget.xml',
            'whatsapp_evolution_ui_utils/static/src/js/text_icon_widget.js',
            'whatsapp_evolution_ui_utils/static/src/xml/text_icon_widget.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}