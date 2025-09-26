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
        Adiciona os membros corretos ao canal e o afixa.
        CORRIGIDO: Usa uma abordagem mais compatível para afixar o canal.
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
        new_partners = [p for p in members_to_add if p.id not in current_member_ids]

        if new_partners:
            channel.write({
                'channel_member_ids': [Command.create({'partner_id': p.id}) for p in new_partners]
            })

        # --- INÍCIO DA CORREÇÃO DO 'PIN' ---
        # Afixa o canal para os membros internos (não para o contato do WhatsApp)
        internal_partners_to_pin = [p for p in members_to_add if p.id != partner.id]
        for p in internal_partners_to_pin:
            member = channel.channel_member_ids.filtered(lambda m: m.partner_id == p)
            if member:
                member.write({'is_pinned': True})
        # --- FIM DA CORREÇÃO DO 'PIN' ---

    # ============================ INÍCIO DA CORREÇÃO FINAL ============================
    def _notify_thread(self, message, msg_vals=False, **kwargs):
        whatsapp_channels = self.filtered(lambda c: c.channel_type == 'whatsapp')
        other_channels = self - whatsapp_channels

        if other_channels:
            super(DiscussChannel, other_channels)._notify_thread(message, msg_vals, **kwargs)

        for channel in whatsapp_channels:
            if self.env.context.get('from_webhook') or (msg_vals and msg_vals.get('author_id') == channel.whatsapp_partner_id.id):
                continue
            
            partner = channel.whatsapp_partner_id
            
            if not partner.mobile:
                _logger.warning("Não foi possível enviar mensagem: Contato '%s' não possui número de celular.", partner.name)
                message.sudo().write({'whatsapp_status': 'failed'})
                continue

            try:
                # PONTO CHAVE DA CORREÇÃO FINAL: Limpa o número para o formato que a API espera (apenas dígitos)
                number_to_send = ''.join(filter(str.isdigit, partner.mobile))
                
                body = html2plaintext(msg_vals.get('body', ''))
                attachments = self.env['ir.attachment'].browse(msg_vals.get('attachment_ids', []))

                if attachments:
                    first_attachment = attachments[0]
                    channel.whatsapp_instance_id.send_attachment(
                        number_to_send, first_attachment, caption=body, partner=partner
                    )
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
                _logger.error("Falha ao enviar mensagem do canal #%s para o WhatsApp: %s", channel.id, e)
                message.sudo().write({'whatsapp_status': 'failed'})
        
        return True
    # ============================ FIM DA CORREÇÃO FINAL ============================

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