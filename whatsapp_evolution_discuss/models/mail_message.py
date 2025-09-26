# -*- coding: utf-8 -*-
from odoo import fields, models

class MailMessage(models.Model):
    _inherit = 'mail.message'

    whatsapp_status = fields.Selection([
        ('sent', 'Sent'),
        ('failed', 'Failed')
    ], string="WhatsApp Status", copy=False)