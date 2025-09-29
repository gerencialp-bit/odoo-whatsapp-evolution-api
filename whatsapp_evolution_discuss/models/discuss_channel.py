# -*- coding: utf-8 -*-
from odoo import api, fields, models, _ as odoo_t, Command
from odoo.tools import html2plaintext
from odoo.exceptions import UserError
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

                # ======================= INÍCIO DA ALTERAÇÃO (RESPOSTAS) ======================= 
                # Verifica se a mensagem é uma resposta a outra 
                quoted_message = None 
                if msg_vals.get('parent_id'): 
                    quoted_message = self.env['mail.message'].browse(msg_vals['parent_id']) 
                # ======================== FIM DA ALTERAÇÃO (RESPOSTAS) ========================= 
                
                # ======================= INÍCIO DA CORREÇÃO =======================
                remote_message_id = None
                log_message = None # <-- Variável para capturar o log

                if attachments:
                    first_attachment = attachments[0]
                    # ======================= INÍCIO DA CORREÇÃO ======================= 
                    # Passa o 'quoted_message' também para o send_attachment 
                    log_message, remote_message_id = channel.whatsapp_instance_id.send_attachment( 
                        number_to_send, first_attachment, caption=body, partner=partner, quoted_message=quoted_message 
                    ) 
                    # ======================== FIM DA CORREÇÃO =========================                     # Envia anexos subsequentes sem esperar por IDs
                    for attachment in attachments[1:]:
                        channel.whatsapp_instance_id.send_attachment(
                            number_to_send, attachment, partner=partner
                        )
                elif body:
                    # ======================= INÍCIO DA CORREÇÃO =======================
                    # Capturamos o log retornado por send_text
                    log_message, remote_message_id = channel.whatsapp_instance_id.send_text(
                        number_to_send, body, partner=partner, quoted_message=quoted_message
                    )
                    # ======================== FIM DA CORREÇÃO =========================

                # Atualiza a mensagem do Odoo com o ID retornado pela API
                if remote_message_id:
                    message.sudo().write({
                        'whatsapp_status': 'sent',
                        'whatsapp_message_id_str': remote_message_id
                    })
                    
                    # ======================= INÍCIO DA CORREÇÃO =======================
                    # Agora, se foi uma resposta, atualizamos o log que acabamos de criar.
                    if quoted_message and log_message:
                        # Precisamos encontrar o log da mensagem original
                        original_log = self.env['whatsapp.message'].search([
                            ('message_id', '=', quoted_message.whatsapp_message_id_str)
                        ], limit=1)
                        if original_log:
                            log_message.sudo().write({'quoted_message_id': original_log.id})
                    # ======================== FIM DA CORREÇÃO =========================

                    _logger.info("Mensagem do canal #%s enviada para o WhatsApp com ID: %s.", channel.id, remote_message_id)
                else:
                    # Se remote_message_id for None, significa que o envio falhou na camada inferior
                    raise UserError(odoo_t("A API não retornou um ID de mensagem para a mensagem enviada."))

                # ======================== FIM DA CORREÇÃO ========================= 

            except Exception as e:
                _logger.error("Falha ao enviar mensagem do canal #%s para o WhatsApp: %s", channel.id, e, exc_info=True)
                message.sudo().write({'whatsapp_status': 'failed'})
         
        return True 
    
    def _whatsapp_send_reaction(self, reaction):
        """
        Envia uma reação para o WhatsApp. Agora só é chamado na criação.
        """
        _logger.info(f"Método _whatsapp_send_reaction chamado para o canal #{self.id} com a reação ID #{reaction.id}")
        self.ensure_one()

        if self.channel_type != 'whatsapp' or reaction.partner_id == self.whatsapp_partner_id:
            return
        
        original_message = reaction.message_id
        if not original_message.whatsapp_message_id_str:
            return
        
        try:
            number_to_send = self.whatsapp_partner_id._get_whatsapp_formatted_number()
            
            payload = {
                "key": {
                    "remoteJid": f"{number_to_send}@s.whatsapp.net",
                    "fromMe": original_message.author_id != self.whatsapp_partner_id,
                    "id": original_message.whatsapp_message_id_str,
                },
                "reaction": reaction.content
            }

            reacted_message_log = self.env['whatsapp.message'].search([
                ('message_id', '=', original_message.whatsapp_message_id_str)
            ], limit=1)

            self.whatsapp_instance_id.send_reaction(
                number_to_send,
                payload,
                partner=self.whatsapp_partner_id,
                reacted_message_log=reacted_message_log
            )
            _logger.info("Reação '%s' enviada e logada com sucesso.", reaction.content)

        except Exception as e:
            _logger.error("Falha ao enviar reação do canal #%s para o WhatsApp: %s", self.id, e, exc_info=True)