# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

class MailMessageReaction(models.Model):
    _inherit = 'mail.message.reaction'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Sobrescreve o método create para interceptar a criação de reações e
        enviá-las para o WhatsApp em tempo real.
        """
        # 1. Cria os registros de reação normalmente
        reactions = super().create(vals_list)

        # 2. Itera sobre as reações recém-criadas para enviá-las
        for reaction in reactions:
            try:
                message = reaction.message_id
                # Garante que estamos no contexto de um canal
                if not message or not message.res_id or message.model != 'discuss.channel':
                    continue

                channel = self.env['discuss.channel'].browse(message.res_id)
                
                # Chama o método de envio que já temos no modelo do canal
                if channel and channel.channel_type == 'whatsapp':
                    _logger.info("Reação criada no canal #%s. Tentando enviar para o WhatsApp.", channel.id)
                    # ======================= INÍCIO DA CORREÇÃO =======================
                    # Chama o método refatorado passando o objeto reaction
                    channel._whatsapp_send_reaction(reaction=reaction)
                    # ======================== FIM DA CORREÇÃO =========================

            except Exception as e:
                _logger.error(
                    "Falha ao processar o envio de reação para o WhatsApp após a criação. Reação ID: %s. Erro: %s",
                    reaction.id, e, exc_info=True
                )
        
        return reactions