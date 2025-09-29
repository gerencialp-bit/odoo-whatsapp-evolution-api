# -*- coding: utf-8 -*-
from odoo import fields, models

class MailMessage(models.Model):
    _inherit = 'mail.message'

    whatsapp_status = fields.Selection([
        ('sent', 'Sent'),
        ('failed', 'Failed')
    ], string="WhatsApp Status", copy=False)
    
    # ======================= INÍCIO DA ALTERAÇÃO =======================
    whatsapp_message_id_str = fields.Char(
        string="WhatsApp Message ID",
        copy=False,
        index=True,
        help="O ID da mensagem no sistema do WhatsApp. Usado para rastrear respostas e reações."
    )
    # ======================== FIM DA ALTERAÇÃO =========================
