# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request
from odoo.addons.whatsapp_contact_management.controllers.main import ContactWebhookController

_logger = logging.getLogger(__name__)

class DiscussWebhookController(ContactWebhookController):

    def _post_message_in_discuss_channel(self, instance, message_data, partner):
        """
        CORRIGIDO: Implementa a lógica para postar a mensagem no canal do Discuss,
        atribuindo o autor correto com base na direção da mensagem (entrada/saída).
        """
        if not partner:
            return

        try:
            channel = request.env['discuss.channel'].sudo()._find_or_create_whatsapp_channel(partner, instance)

            message_content = message_data.get('message', {})
            body = message_content.get('conversation') or message_content.get('extendedTextMessage', {}).get('text', '')
            
            # --- INÍCIO DA LÓGICA DE DEFINIÇÃO DO AUTOR ---
            is_from_me = message_data.get('key', {}).get('fromMe', False)
            author_id = False

            if is_from_me:
                # Mensagem de SAÍDA: O autor é o usuário do Odoo dono da instância.
                if instance.user_id and instance.user_id.partner_id:
                    author_id = instance.user_id.partner_id.id
                else:
                    _logger.warning(
                        "Mensagem de saída (webhook) da instância '%s' não pôde ser postada no Discuss por falta de um usuário responsável vinculado.",
                        instance.name
                    )
                    return # Interrompe para não postar com o autor errado
            else:
                # Mensagem de ENTRADA: O autor é o contato externo.
                author_id = partner.id
            
            if not author_id:
                _logger.error("Não foi possível determinar um autor válido para a mensagem do webhook no canal do Discuss.")
                return
            # --- FIM DA LÓGICA DE DEFINIÇÃO DO AUTOR ---

            ctx = {'from_webhook': True}

            channel.with_context(**ctx).message_post(
                body=body,
                author_id=author_id, # Usa o autor que acabamos de determinar
                message_type='comment',
                subtype_xmlid='mail.mt_comment'
            )
            _logger.info(
                "Mensagem do webhook postada com sucesso no canal do Discuss #%s com o autor correto (ID: %s).", channel.id, author_id
            )
        except Exception as e:
            _logger.error("Falha ao postar mensagem do webhook no canal do Discuss: %s", e, exc_info=True)