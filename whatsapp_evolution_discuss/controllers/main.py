# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request
from odoo.addons.whatsapp_contact_management.controllers.main import ContactWebhookController

_logger = logging.getLogger(__name__)

class DiscussWebhookController(ContactWebhookController):

    def _post_message_in_discuss_channel(self, instance, message_data, partner):
        """
        Implementa a lógica para postar a mensagem no canal do Discuss.
        Esta função é chamada pelo controller pai (contact_management) depois que o contato
        foi criado/encontrado e o log base da mensagem foi salvo.
        """
        if not partner:
            return

        try:
            channel = request.env['discuss.channel'].sudo()._find_or_create_whatsapp_channel(partner, instance)

            message_content = message_data.get('message', {})
            body = message_content.get('conversation') or message_content.get('extendedTextMessage', {}).get('text', '')
            
            ctx = {'from_webhook': True}

            channel.with_context(**ctx).message_post(
                body=body,
                author_id=partner.id,
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )
            _logger.info(
                "Mensagem do webhook postada com sucesso no canal do Discuss #%s.", channel.id
            )
        except Exception as e:
            _logger.error("Falha ao postar mensagem do webhook no canal do Discuss: %s", e, exc_info=True)