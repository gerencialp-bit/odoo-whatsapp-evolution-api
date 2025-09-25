# -*- coding: utf-8 -*-

import logging
import base64
import requests
from odoo import http, fields, _ # <-- 'fields' e '_' adicionados aqui
from odoo.http import request
from odoo.addons.whatsapp_evolution_base.controllers.webhook_controller import WhatsappWebhookController

_logger = logging.getLogger(__name__)

class ContactWebhookController(WhatsappWebhookController):

    @http.route('/whatsapp/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def receive_webhook(self):
        """
        Sobrescreve o webhook base para adicionar a lógica de criação e associação de contatos.
        """
        response = super(ContactWebhookController, self).receive_webhook()

        try:
            payload = request.get_json_data()
            instance_name = payload.get('instance')
            
            instance = request.env['whatsapp.instance'].sudo().search([('name', '=', instance_name)], limit=1)
            if not instance:
                return response

            event = payload.get('event')
            if event == 'messages.upsert':
                message_data = payload.get('data', {})
                self._process_message_for_contact_linking(instance, message_data)

        except Exception as e:
            _logger.error("Erro na camada de gerenciamento de contatos do webhook: %s", e, exc_info=True)

        return response

    def _set_partner_image_from_api(self, partner, instance, phone_number):
        """
        Busca a foto de perfil da Evolution API, faz o download e a salva no registro do parceiro.
        """
        if not all([partner, instance, phone_number]):
            return

        try:
            api_response = request.env['whatsapp.evolution.api'].sudo()._api_fetch_profile_picture_url(instance, phone_number)
            pic_url = api_response.get('profilePictureUrl')

            if pic_url:
                image_response = requests.get(pic_url, timeout=20)
                image_response.raise_for_status()
                image_b64 = base64.b64encode(image_response.content)
                partner.sudo().write({'image_1920': image_b64})
                _logger.info("Foto de perfil atualizada para o contato '%s' (ID: %s) a partir da URL.", partner.name, partner.id)

        except Exception as e:
            _logger.warning(
                "Não foi possível buscar a foto de perfil para o contato %s (%s). Erro: %s",
                partner.name, phone_number, e
            )

    def _process_message_for_contact_linking(self, instance, message_data):
        """
        Orquestra a busca/criação do contato e a vinculação com o registro de mensagem.
        """
        partner = self._find_or_create_partner_from_message(instance, message_data)

        if partner:
            message_id = message_data.get('key', {}).get('id')
            if message_id:
                WhatsappMessage = request.env['whatsapp.message'].sudo()
                message = WhatsappMessage.search([
                    ('message_id', '=', message_id),
                    ('instance_id', '=', instance.id)
                ], limit=1)
                
                if message and not message.partner_id:
                    message.write({'partner_id': partner.id})
                    _logger.info(
                        "Mensagem '%s' associada ao contato '%s' (ID: %s)",
                        message_id, partner.name, partner.id
                    )

    def _find_or_create_partner_from_message(self, instance, message_data):
        """
        Encontra ou cria um res.partner a partir de um payload de mensagem,
        respeitando as regras de privacidade, promovendo contatos quando necessário
        e registrando ações no chatter.
        """
        key = message_data.get('key', {})
        
        # Determina o JID do contato externo, seja em conversa privada ou grupo
        if key.get('fromMe'):
            remote_jid = key.get('remoteJid') # Em mensagens de saída, o JID é o destinatário
        else:
            # Em mensagens de entrada, pode ser um grupo ou uma conversa privada
            remote_jid = key.get('participant') or key.get('remoteJid')
        
        if not remote_jid or '@g.us' in remote_jid:
            return request.env['res.partner']

        phone_number = remote_jid.split('@')[0]
        Partner = request.env['res.partner'].sudo()

        try:
            normalized_phone = Partner.phone_format(phone_number)
        except Exception:
            _logger.warning("Não foi possível formatar o número '%s'. Usando o valor original.", phone_number)
            normalized_phone = phone_number

        partner = Partner.search([
            '|', ('phone', '=', normalized_phone), ('mobile', '=', normalized_phone)
        ], limit=1)

        # ==================== INÍCIO DA NOVA LÓGICA ====================
        if partner:
            # LÓGICA DE PROMOÇÃO: Se a instância da empresa interage com um contato privado, ele se torna da empresa.
            if partner.is_private and instance.instance_type == 'company':
                original_owner_name = partner.owner_user_id.name or _('um usuário desconhecido')
                partner.write({
                    'is_private': False,
                    'promoted_date': fields.Datetime.now(),
                })
                partner.message_post(body=_(
                    "Este contato foi promovido a um contato da empresa devido à interação com a instância '%(instance_name)s'. O proprietário original era %(owner_name)s.",
                    instance_name=instance.name,
                    owner_name=original_owner_name
                ))
                _logger.info("Contato '%s' (ID: %s) promovido a contato da empresa pela instância '%s'.", partner.name, partner.id, instance.name)
            
            # Lógica de atualização existente (imagem de perfil, etc.)
            if not partner.image_1920:
                self._set_partner_image_from_api(partner, instance, normalized_phone)
            return partner

        # LÓGICA DE CRIAÇÃO (para contatos que não existem)
        sender_name = message_data.get('pushName') or phone_number
        vals = {
            'name': sender_name,
            'mobile': normalized_phone,
            'whatsapp_instance_id': instance.id,
            'whatsapp_verified': True,
            'whatsapp_verified_date': fields.Datetime.now(),
        }

        # Define a privacidade do novo contato com base no tipo da instância
        if instance.instance_type == 'user' and instance.user_id:
            vals.update({'is_private': True, 'owner_user_id': instance.user_id.id})
            contact_type_msg = _('privado e atribuído a %(user_name)s', user_name=instance.user_id.name)
        else:
            vals.update({'is_private': False})
            contact_type_msg = _('da empresa')

        try:
            new_partner = Partner.create(vals)
            # Log no chatter do novo contato
            new_partner.message_post(body=_(
                "Contato criado como %(contact_type)s a partir de uma mensagem da instância do WhatsApp '%(instance_name)s'.",
                contact_type=contact_type_msg,
                instance_name=instance.name
            ))
            _logger.info(
                "Webhook: Criado contato %s '%s' para o número %s pela instância '%s'.",
                'privado' if vals.get('is_private') else 'público',
                new_partner.name,
                normalized_phone,
                instance.name
            )
            self._set_partner_image_from_api(new_partner, instance, normalized_phone)
            return new_partner
        except Exception as e:
            _logger.error("Webhook: Falha ao criar contato para %s. Erro: %s", normalized_phone, e)
            return request.env['res.partner']
        # ==================== FIM DA NOVA LÓGICA ====================