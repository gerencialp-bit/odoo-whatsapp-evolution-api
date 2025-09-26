# whatsapp_contact_management/controllers/main.py

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
        1. Encontra/cria o parceiro (para mensagens de entrada E saída).
        2. Passa o parceiro para o método base criar o log da mensagem.
        3. Passa o parceiro para a camada do Discuss postar no canal.
        """
        try:
            payload = request.get_json_data()
            instance_name = payload.get('instance')
            
            instance = request.env['whatsapp.instance'].sudo().search([('name', '=', instance_name)], limit=1)
            if not instance:
                _logger.warning(f"Webhook ignorado: Instância '{instance_name}' não encontrada.")
                return {'status': 'ok', 'message': 'Instance not found'}

            event = payload.get('event')
            partner = request.env['res.partner']

            if event == 'messages.upsert':
                message_data = payload.get('data', {})
                # A lógica de encontrar/criar o parceiro agora funciona para ambas as direções
                partner = self._find_or_create_partner_from_message(instance, message_data)

            if partner:
                request.update_context(webhook_partner_id=partner.id)

            response = super(ContactWebhookController, self).receive_webhook()
            
            # A postagem no Discuss agora também ocorrerá para mensagens de saída
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
        """
        CORRIGIDO: Encontra ou cria o parceiro tanto para mensagens de entrada quanto de saída.
        """
        key = message_data.get('key', {})
        is_from_me = key.get('fromMe', False)

        # Determina o JID do "outro" participante da conversa
        if is_from_me:
            # Mensagem de SAÍDA: O parceiro é o destinatário (remoteJid)
            partner_jid = key.get('remoteJid')
        else:
            # Mensagem de ENTRADA: O parceiro é o remetente (participant ou remoteJid)
            partner_jid = key.get('participant') or key.get('remoteJid')

        # Se não há um JID de parceiro ou é uma mensagem de grupo genérica, não faz nada
        if not partner_jid or '@g.us' in partner_jid:
            return request.env['res.partner']

        phone_number_only = partner_jid.split('@')[0]
        Partner = request.env['res.partner'].sudo()
        sanitized_number = ''.join(filter(str.isdigit, phone_number_only))
        
        domain = ['|', ('mobile', 'ilike', sanitized_number), ('phone', 'ilike', sanitized_number)]
        partner = Partner.search(domain, limit=1)

        if len(partner) > 1:
            exact_partner = Partner.search(['|', ('mobile', '=', '+' + sanitized_number), ('phone', '=', '+' + sanitized_number)], limit=1)
            if exact_partner:
                partner = exact_partner
                
        if partner:
            # Não faz a lógica de promoção para mensagens de saída
            if not is_from_me and partner.is_private and instance.instance_type == 'company':
                pass # Lógica de promoção, se houver
            
            # Busca foto de perfil apenas para mensagens de entrada (onde o pushName está disponível)
            if not is_from_me and not partner.image_1920:
                self._set_partner_image_from_api(partner, instance, partner_jid)
            return partner

        # Lógica de criação de contato (geralmente para mensagens de entrada)
        # Para mensagens de saída, o contato já deveria existir. Se não existir, criamos.
        # O pushName em mensagens de saída é o do remetente, não do destinatário.
        # Usar o número de telefone como nome é um fallback seguro.
        partner_name = message_data.get('pushName') if not is_from_me else phone_number_only
        
        vals = {
            'name': partner_name,
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
            if not is_from_me:
                self._set_partner_image_from_api(new_partner, instance, partner_jid)
            return new_partner
        except Exception as e:
            _logger.error("Webhook: Falha ao criar contato para %s. Erro: %s", sanitized_number, e)
            return request.env['res.partner']