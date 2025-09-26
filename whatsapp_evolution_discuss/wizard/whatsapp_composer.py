# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class WhatsappEvolutionComposer(models.TransientModel):
    _name = 'whatsapp.evolution.composer'
    _description = 'WhatsApp Composer'

    @api.model
    def default_get(self, fields):
        res = super(WhatsappEvolutionComposer, self).default_get(fields)
        if self.env.context.get('active_model') and self.env.context.get('active_id'):
            res['model'] = self.env.context['active_model']
            res['res_id'] = self.env.context['active_id']
            record = self.env[res['model']].browse(res['res_id'])
            if 'partner_id' in record and record.partner_id:
                res['partner_id'] = record.partner_id.id
        
        instance = self.env['whatsapp.instance'].search([('status', '=', 'connected')], limit=1)
        if instance:
            res['instance_id'] = instance.id
        return res

    partner_id = fields.Many2one('res.partner', string="Recipient", required=True)
    body = fields.Text(string="Message", required=True)
    instance_id = fields.Many2one(
        'whatsapp.instance', string="Send From", required=True,
        domain="[('status', '=', 'connected')]"
    )
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")

    model = fields.Char('Related Document Model')
    res_id = fields.Integer('Related Document ID')
    
    def action_send_message(self):
        self.ensure_one()
        if not self.body and not self.attachment_ids:
            raise UserError(_("Please enter a message or add an attachment."))
        
        record = self.env[self.model].browse(self.res_id) if self.model and self.res_id else None

        try:
            # PONTO CHAVE DA CORREÇÃO: Usamos self.partner_id que é o parceiro do wizard 
            phone_number = self.partner_id._get_whatsapp_formatted_number()
            partner_to_send = self.partner_id # Define a variável corretamente 

            if self.attachment_ids:
                first_attachment = self.attachment_ids[0]
                self.instance_id.send_attachment(phone_number, first_attachment, caption=self.body, partner=partner_to_send)
                for attachment in self.attachment_ids[1:]:
                     self.instance_id.send_attachment(phone_number, attachment, partner=partner_to_send)
            else:
                self.instance_id.send_text(phone_number, self.body, partner=partner_to_send)
            
            if record:
                chatter_body = _("WhatsApp message sent to %s:\n%s") % (partner_to_send.name, self.body)
                record.message_post(
                    body=chatter_body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                    attachment_ids=self.attachment_ids.ids
                )
        except Exception as e:
            raise UserError(_("Failed to send WhatsApp message: %s") % e)

        return {'type': 'ir.actions.act_window_close'}