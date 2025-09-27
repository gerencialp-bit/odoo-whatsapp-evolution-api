# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.tools import html2plaintext  # <-- CORREÇÃO: Importa a ferramenta correta
import logging

_logger = logging.getLogger(__name__)

class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    channel_type = fields.Selection(
        selection_add=[('whatsapp', 'WhatsApp Conversation')],
        ondelete={'whatsapp': 'cascade'})
    
    whatsapp_instance_id = fields.Many2one('whatsapp.instance', string="WhatsApp Instance", readonly=True)
    whatsapp_partner_id = fields.Many2one('res.partner', string="WhatsApp Partner", readonly=True)

    @api.model
    def _find_or_create_whatsapp_channel(self, partner, instance):
        """
        Encontra ou cria um canal do tipo WhatsApp para um parceiro e uma instância.
        """
        channel = self.search([
            ('channel_type', '=', 'whatsapp'),
            ('whatsapp_partner_id', '=', partner.id),
            ('whatsapp_instance_id', '=', instance.id)
        ], limit=1)

        if channel:
            self._add_members_to_whatsapp_channel(channel, partner, instance)
            return channel

        channel = self.create({
            'name': f"WhatsApp - {partner.name}",
            'channel_type': 'whatsapp',
            'whatsapp_partner_id': partner.id,
            'whatsapp_instance_id': instance.id,
        })
        
        self._add_members_to_whatsapp_channel(channel, partner, instance)
        _logger.info("Criado novo canal de WhatsApp #%s para o parceiro '%s' (ID: %s)", channel.id, partner.name, partner.id)
        return channel
    
    def _add_members_to_whatsapp_channel(self, channel, partner, instance):
        """
        Adiciona os membros corretos ao canal e o afixa para novos membros.
        """
        members_to_add = {partner}
        if instance.user_id:
            members_to_add.add(instance.user_id.partner_id)
         
        if instance.instance_type == 'company' and not instance.user_id:
            admin_group = self.env.ref('base.group_system', raise_if_not_found=False)
            if admin_group:
                admin_users = self.env['res.users'].search([('groups_id', 'in', admin_group.id)])
                for user in admin_users:
                    members_to_add.add(user.partner_id)

        current_member_ids = channel.channel_member_ids.mapped('partner_id').ids
        # Filtra apenas os parceiros que ainda não são membros do canal.
        new_partners = [p for p in members_to_add if p.id not in current_member_ids]

        if new_partners:
            commands = []
            for p in new_partners:
                # Para usuários internos, afixa o canal na criação. O contato externo não precisa disso.
                is_internal = p.id != partner.id
                commands.append(Command.create({'partner_id': p.id, 'is_pinned': is_internal}))
            
            channel.write({
                'channel_member_ids': commands
            })

    # ============================ INÍCIO DA CORREÇÃO (REAL-TIME E ENVIO) ============================
    def _notify_thread(self, message, msg_vals=False, **kwargs):
        # PRIMEIRO, CHAMA A LÓGICA ORIGINAL DO ODOO PARA TODOS OS CANAIS.
        # Isso garante que a notificação via bus.bus seja enviada para a interface,
        # resolvendo o problema de não atualização em tempo real.
        super(DiscussChannel, self)._notify_thread(message, msg_vals, **kwargs)

        # AGORA, EXECUTA A LÓGICA DE ENVIO PARA O WHATSAPP APENAS NOS CANAIS RELEVANTES.
        whatsapp_channels = self.filtered(lambda c: c.channel_type == 'whatsapp')

        for channel in whatsapp_channels:
            # Ignora a lógica de envio se a mensagem veio do webhook (evita loop)
            # ou se o autor da mensagem no Odoo for o próprio contato do WhatsApp.
            is_from_contact = msg_vals and msg_vals.get('author_id') == channel.whatsapp_partner_id.id
            if self.env.context.get('from_webhook') or is_from_contact:
                continue
            
            partner = channel.whatsapp_partner_id
            
            # Validação do número de celular
            if not partner.mobile:
                _logger.warning("Não foi possível enviar mensagem via WhatsApp: Contato '%s' não possui número de celular.", partner.name)
                message.sudo().write({'whatsapp_status': 'failed'})
                continue

            try:
                # Obtém o número formatado usando o método já existente no módulo de contato
                number_to_send = partner._get_whatsapp_formatted_number()
                
                # Extrai texto e anexos dos valores da mensagem
                body = html2plaintext(msg_vals.get('body', ''))
                # Em vez de usar os `msg_vals` (que contêm comandos), pegamos os anexos 
                # diretamente do registro `message` que já foi criado e processado. 
                attachments = message.attachment_ids

                # Lógica de envio
                if attachments:
                    # Envia o primeiro anexo com a legenda (corpo da mensagem)
                    first_attachment = attachments[0]
                    channel.whatsapp_instance_id.send_attachment(
                        number_to_send, first_attachment, caption=body, partner=partner
                    )
                    # Envia os anexos restantes sem legenda
                    for attachment in attachments[1:]:
                        channel.whatsapp_instance_id.send_attachment(
                            number_to_send, attachment, partner=partner
                        )
                elif body:
                    channel.whatsapp_instance_id.send_text(
                        number_to_send, body, partner=partner
                    )
                
                message.sudo().write({'whatsapp_status': 'sent'})
                _logger.info("Mensagem do canal #%s enviada com sucesso para o WhatsApp.", channel.id)

            except Exception as e:
                _logger.error("Falha ao enviar mensagem do canal #%s para o WhatsApp: %s", channel.id, e, exc_info=True)
                message.sudo().write({'whatsapp_status': 'failed'})
        
        # O retorno do super() já foi tratado, então retornamos True.
        return True
    # ============================ FIM DA CORREÇÃO (REAL-TIME E ENVIO) ============================

    @api.model
    def get_or_create_whatsapp_channel_for_partner(self, partner_id):
        """
        Método chamado pelo frontend para iniciar uma conversa.
        """
        partner = self.env['res.partner'].browse(partner_id)
        if not partner.mobile:
            raise UserError(_("O contato selecionado não possui um número de celular."))

        instance = self.env['whatsapp.instance'].search([('status', '=', 'connected')], limit=1)
        if not instance:
            raise UserError(_("Nenhuma instância do WhatsApp conectada e disponível foi encontrada."))
        
        channel = self._find_or_create_whatsapp_channel(partner, instance)
        
        return channel.channel_info('whatsapp_channel_created')[0]