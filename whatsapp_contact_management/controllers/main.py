# -*- coding: utf-8 -*-

import logging
import base64
import requests
from odoo import http, fields, _
from odoo.http import request
from odoo.addons.whatsapp_evolution_base.controllers.webhook_controller import WhatsappWebhookController

_logger = logging.getLogger(__name__)

class ContactWebhookController(WhatsappWebhookController):

    @http.route('/whatsapp/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def receive_webhook(self):
        """
        Versão final e corrigida do webhook.
        1. Encontra/cria o parceiro.
        2. Passa o parceiro para o método base criar o log da mensagem.
        3. Passa o parceiro para a camada do Discuss postar no canal.
        """
        try:
            payload = request.get_json_data()
            instance_name = payload.get('instance')
            
            # PONTO CHAVE DA CORREÇÃO: Usar request.env em vez de self.env 
            instance = request.env['whatsapp.instance'].sudo().search([('name', '=', instance_name)], limit=1)
            if not instance:
                _logger.warning(f"Webhook ignorado: Instância '{instance_name}' não encontrada.")
                return {'status': 'ok', 'message': 'Instance not found'}

            event = payload.get('event')
            partner = request.env['res.partner'] # Inicia partner como vazio 

            if event == 'messages.upsert':
                message_data = payload.get('data', {})
                partner = self._find_or_create_partner_from_message(instance, message_data)

            # Adiciona o partner_id ao contexto para que as camadas seguintes possam usá-lo 
            if partner:
                # PONTO CHAVE DA CORREÇÃO: Usar o método correto para atualizar o contexto 
                request.update_context(webhook_partner_id=partner.id) 

            # Chama o método original (do módulo base) para criar o whatsapp.message 
            response = super(ContactWebhookController, self).receive_webhook() 
            
            # Chama a camada do Discuss para postar no canal 
            if event == 'messages.upsert' and partner:
                self._post_message_in_discuss_channel(instance, payload.get('data', {}), partner) 

        except Exception as e:
            _logger.error("Erro na camada de gerenciamento de contatos do webhook: %s", e, exc_info=True)
            request.env.cr.rollback()
            return {'status': 'error', 'message': str(e)}

        return response 

    def _post_message_in_discuss_channel(self, instance, message_data, partner):
        """
        Este método é um "placeholder" que é implementado pelo módulo whatsapp_evolution_discuss.
        """
        pass 

    def _set_partner_image_from_api(self, partner, instance, phone_number):
        # ... (este método permanece o mesmo) 
        if not all([partner, instance, phone_number]):
            return 
        try:
            clean_number = phone_number.split('@')[0]
            api_response = request.env['whatsapp.evolution.api'].sudo()._api_fetch_profile_picture_url(instance, clean_number)
            pic_url = api_response.get('profilePictureUrl')
            if pic_url:
                image_response = requests.get(pic_url, timeout=20)
                image_response.raise_for_status()
                image_b64 = base64.b64encode(image_response.content)
                partner.sudo().write({'image_1920': image_b64})
        except Exception as e:
            _logger.warning("Não foi possível buscar a foto de perfil para %s (%s). Erro: %s", partner.name, phone_number, e)

    def _find_or_create_partner_from_message(self, instance, message_data):
        # ... (este método permanece o mesmo da versão anterior, pois sua lógica de busca e criação estava correta) 
        key = message_data.get('key', {})
        if key.get('fromMe'):
            return request.env['res.partner']
        sender_jid = key.get('participant') or key.get('remoteJid')
        if not sender_jid or '@g.us' in sender_jid:
            return request.env['res.partner']
        phone_number_only = sender_jid.split('@')[0]
        Partner = request.env['res.partner'].sudo()
        sanitized_number = ''.join(filter(str.isdigit, phone_number_only))
        domain = ['|', ('mobile', 'ilike', sanitized_number), ('phone', 'ilike', sanitized_number)]
        partner = Partner.search(domain, limit=1)
        if len(partner) > 1:
            exact_partner = Partner.search(['|', ('mobile', '=', '+' + sanitized_number), ('phone', '=', '+' + sanitized_number)], limit=1)
            if exact_partner:
                partner = exact_partner
        if partner:
            if partner.is_private and instance.instance_type == 'company':
                # ... Lógica de promoção ... 
                pass
            if not partner.image_1920:
                self._set_partner_image_from_api(partner, instance, sender_jid)
            return partner
        sender_name = message_data.get('pushName') or phone_number_only
        vals = {
            'name': sender_name,
            'mobile': f"+{sanitized_number}",
            'whatsapp_instance_id': instance.id,
            'whatsapp_verified': True,
            'whatsapp_verified_date': fields.Datetime.now(),
        }
        if instance.instance_type == 'user' and instance.user_id:
            vals.update({'is_private': True, 'owner_user_id': instance.user_id.id})
        else:
            vals.update({'is_private': False})
        try:
            new_partner = Partner.create(vals)
            new_partner.message_post(body=_("Contato criado a partir de uma mensagem do WhatsApp."))
            self._set_partner_image_from_api(new_partner, instance, sender_jid)
            return new_partner
        except Exception as e:
            _logger.error("Webhook: Falha ao criar contato para %s. Erro: %s", sanitized_number, e)
            return request.env['res.partner']