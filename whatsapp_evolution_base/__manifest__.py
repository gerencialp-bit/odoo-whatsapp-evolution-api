# -*- coding: utf-8 -*- 
{ 
    'name': "WhatsApp Evolution API - Base Connector", 
    'summary': "Módulo base para integração do Odoo com a Evolution API.", 
    'description': "Gerenciamento de instâncias, webhook e logs de mensagens.", 
    'author': "Odoo Evolution Architect", 
    'website': " `https://www.yourcompany.com` ", 
    'category': 'Discuss', 
    'version': '1.5', # Incrementando a versão 
    'depends': ['mail', 'contacts', 'web', 'phone_validation'], # <-- DEPENDÊNCIA ADICIONADA AQUI 
    'data': [ 
        'security/ir.model.access.csv', 
        'data/evolution_api_config_data.xml',
        'data/whatsapp_webhook_event_data.xml', # <-- ADICIONADO 
        'views/whatsapp_config_settings_views.xml', 
        # --- ORDEM CORRIGIDA --- 
        # 1. Carregar as views e suas actions PRIMEIRO 
        'views/whatsapp_instance_views.xml', 
        'views/whatsapp_message_views.xml', 
        # 2. Carregar os menus que USAM essas actions DEPOIS 
        'views/evolution_menus.xml', 
        # --- FIM DA CORREÇÃO --- 
    ], 
    'assets': { 
        'web.assets_backend': [ 
            'whatsapp_evolution_base/static/src/js/whatsapp_media_widget.js', 
            'whatsapp_evolution_base/static/src/xml/whatsapp_media_widget.xml', 
        ], 
    }, 
    'installable': True, 
    'application': True, 
    'auto_install': False, 
    'license': 'LGPL-3', 
}