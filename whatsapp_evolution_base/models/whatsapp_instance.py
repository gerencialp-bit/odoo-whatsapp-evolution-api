# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.mimetypes import guess_mimetype
import requests
import base64
import json # <-- Importar json
import logging
import json
from datetime import datetime

_logger = logging.getLogger(__name__)

class WhatsappInstance(models.Model):
    _name = 'whatsapp.instance'
    _description = 'WhatsApp Instance'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    mandatory_webhook_events_ids = fields.Many2many(
        'whatsapp.webhook.event',
        'whatsapp_instance_mandatory_event_rel',
        'instance_id', 'event_id',
        string="Eventos Obrigatórios",
        compute='_compute_mandatory_webhook_events',
        readonly=True,
        store=False,
        help="Eventos essenciais para o funcionamento do módulo. Não podem ser desativados."
    )
    optional_webhook_events_ids = fields.Many2many(
        'whatsapp.webhook.event',
        'whatsapp_instance_optional_event_rel',
        'instance_id', 'event_id',
        string="Eventos Opcionais",
        tracking=True
    )
    
    name = fields.Char(string='Instance Name', required=True, tracking=True, copy=False)
    phone_number = fields.Char(string='Phone Number', readonly=True, tracking=True)
    status = fields.Selection([
        ('disconnected', 'Desconectado'),
        ('connecting', 'Conectando'),
        ('connected', 'Conectado'),
        ('error', 'Erro'),
    ], string='Status', default='disconnected', readonly=True, tracking=True)
    profile_picture = fields.Binary(string='Foto do Perfil', readonly=True, attachment=True)
    profile_name = fields.Char(string='Nome do Perfil', readonly=True)
    api_key = fields.Char(string='Chave da API', groups="base.group_system", help="Token da instância na Evolution API.", tracking=True)
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    instance_type = fields.Selection([('company', 'Empresa'), ('user', 'Usuário Individual')],
        string='Tipo da Instância', default='company', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Usuário Responsável', tracking=True)
    message_ids = fields.One2many('whatsapp.message', 'instance_id', string='Histórico de Mensagens')
    contact_count = fields.Integer(string='Contatos', readonly=True)
    chat_count = fields.Integer(string='Chats', readonly=True)
    message_count = fields.Integer(string='Mensagens', readonly=True)
    qrcode_image = fields.Binary(string='QR Code', readonly=True)
    reject_call = fields.Boolean(string="Rejeitar Chamadas", default=False, tracking=True)
    call_rejected_message = fields.Char(string="Mensagem de Rejeição", default="Não posso atender chamadas no momento.", tracking=True)
    ignore_group = fields.Boolean(string="Ignorar Grupos", default=False, tracking=True)
    always_online = fields.Boolean(string="Sempre Online", default=False, tracking=True)
    view_message = fields.Boolean(string="Ler Mensagens Automaticamente", default=True, help="Marca as mensagens como lidas na API.", tracking=True)
    sync_history = fields.Boolean(string="Sincronizar Histórico Completo", default=False, tracking=True)
    view_status = fields.Boolean(string="Visualizar Status", default=False, tracking=True)
    enable_webhook = fields.Boolean(string="Habilitar Webhook", default=True, tracking=True)
    webhook_url = fields.Char(string="Webhook URL", compute='_compute_webhook_url', readonly=True, store=False)
    base64_webhook = fields.Boolean(string="Base64 Webhook", default=False, tracking=True)
    
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'O nome da instância deve ser único!'),
    ]

    # ... (TODOS OS MÉTODOS ANTERIORES PERMANECEM AQUI) ...

    # ======================= INÍCIO DA CORREÇÃO DEFINITIVA DOS MÉTODOS DE ENVIO =======================
    def send_text(self, phone_number, message, partner=None):
        """
        Envia uma mensagem de texto para um NÚMERO JÁ FORMATADO.
        Opcionalmente, associa a mensagem a um parceiro.
        """
        self.ensure_one()
        
        vals = {
            'instance_id': self.id,
            'timestamp': fields.Datetime.now(),
            'message_direction': 'outbound',
            'partner_id': partner.id if partner else None,
            'phone_number': phone_number,
            'message_type': 'conversation',
            'body': message,
        }

        try:
            response = self.env['whatsapp.evolution.api']._api_send_text(self, phone_number, message)
            vals.update({
                'message_id': response.get('key', {}).get('id'),
                'state': 'sent',
                'raw_json': json.dumps(response),
            })
        except Exception as e:
            _logger.error("Falha ao enviar mensagem de texto para %s: %s", phone_number, e)
            vals.update({
                'state': 'failed',
                'raw_json': str(e),
            })
        
        return self.env['whatsapp.message'].create(vals)

    def send_attachment(self, phone_number, attachment, caption='', partner=None):
        """
        Envia um anexo para um NÚMERO JÁ FORMATADO.
        Opcionalmente, associa a mensagem a um parceiro.
        """
        self.ensure_one()
        
        mimetype = attachment.mimetype or guess_mimetype(base64.b64decode(attachment.datas))
        
        if mimetype.startswith('image'):
            mediatype = 'image'
        elif mimetype.startswith('video'):
            mediatype = 'video'
        else:
            mediatype = 'document'

        media_base64 = attachment.datas.decode('utf-8')

        vals = {
            'instance_id': self.id,
            'timestamp': fields.Datetime.now(),
            'message_direction': 'outbound',
            'partner_id': partner.id if partner else None,
            'phone_number': phone_number,
            'media_type': mediatype,
            'body': caption,
            'media_filename': attachment.name,
        }

        try:
            response = self.env['whatsapp.evolution.api']._api_send_media(
                self, phone_number, mediatype, media_base64, caption, attachment.name
            )
            vals.update({
                'message_id': response.get('key', {}).get('id'),
                'state': 'sent',
                'raw_json': json.dumps(response),
            })
        except Exception as e:
            _logger.error("Falha ao enviar anexo para %s: %s", phone_number, e)
            vals.update({
                'state': 'failed',
                'raw_json': str(e),
            })

        return self.env['whatsapp.message'].create(vals)
    # ======================== FIM DA CORREÇÃO DEFINITIVA DOS MÉTODOS DE ENVIO =========================

    @api.depends()
    def _compute_mandatory_webhook_events(self):
        essential_events = [
            self.env.ref('whatsapp_evolution_base.event_messages_upsert', raise_if_not_found=False),
            self.env.ref('whatsapp_evolution_base.event_messages_update', raise_if_not_found=False),
            self.env.ref('whatsapp_evolution_base.event_connection_update', raise_if_not_found=False)
        ]
        valid_events = [event.id for event in essential_events if event]
        for instance in self:
            instance.mandatory_webhook_events_ids = [(6, 0, valid_events)]

    def _get_correct_webhook_config(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if not base_url:
            _logger.error("A URL base do sistema (web.base.url) não está configurada.")
            return None
         
        webhook_url = f"{base_url.rstrip('/')}/whatsapp/webhook"
        mandatory_ids = set(self.mandatory_webhook_events_ids.ids)
        optional_ids = set(self.optional_webhook_events_ids.ids)
        all_event_ids = list(mandatory_ids.union(optional_ids))
        events = self.env['whatsapp.webhook.event'].browse(all_event_ids).mapped('name')
        
        return { "webhook": { "enabled": self.enable_webhook, "url": webhook_url, "webhookByEvents": True, "events": events, "base64": self.base64_webhook } }
    
    @api.depends('name')
    def _compute_webhook_url(self):
        for instance in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            if base_url:
                instance.webhook_url = f"{base_url.rstrip('/')}/whatsapp/webhook"
            else:
                instance.webhook_url = "Configure a URL Base do sistema (web.base.url)"

    @api.model
    def create(self, vals):
        if not self.env.context.get('syncing_instance'):
            _logger.info("Criando a instância '%s' na Evolution API...", vals.get('name'))
            try:
                api_config = self.env['evolution.api.config']._get_config_record()
                base_url = api_config.evolution_api_url
                api_key = api_config.evolution_api_global_key
                if not base_url or not api_key:
                    raise UserError(_("A URL e a Chave Global da API devem ser configuradas."))

                create_payload = {
                    "instanceName": vals.get('name'),
                    "qrcode": False,
                    "integration": "WHATSAPP-BAILEYS",
                    "settings": {
                        "reject_call": vals.get('reject_call', False),
                        "msg_call": vals.get('call_rejected_message', "Não posso atender chamadas no momento."),
                        "groups_ignore": vals.get('ignore_group', False),
                        "always_online": vals.get('always_online', False),
                        "read_messages": vals.get('view_message', True),
                        "read_status": vals.get('view_status', False),
                        "sync_full_history": vals.get('sync_history', False),
                    }
                }
                api_response = self.env['whatsapp.evolution.api']._send_api_request_global(
                    base_url, api_key, 'POST', '/instance/create', payload=create_payload
                )

                instance_token = None
                if isinstance(api_response, dict):
                    hash_data = api_response.get('hash')
                    if isinstance(hash_data, str):
                        instance_token = hash_data
                    elif isinstance(hash_data, dict):
                        instance_token = hash_data.get('apikey')
                    
                    if not instance_token:
                        instance_token = api_response.get('apikey') or api_response.get('token')

                if instance_token:
                    vals['api_key'] = instance_token
                    _logger.info("Instância '%s' criada com sucesso na Evolution API.", vals.get('name'))
                else:
                    _logger.error("A API da Evolution não retornou uma Chave de API (Token) no formato esperado. Resposta: %s", api_response)
                    raise UserError(_("A API da Evolution não retornou uma Chave de API (Token). Resposta: %s") % api_response)

            except Exception as e:
                _logger.error("Falha ao criar a instância '%s' na Evolution API: %s", vals.get('name'), e)
                raise UserError(_(f"Falha ao criar a instância na Evolution API. Erro: {e}"))
         
        instance = super(WhatsappInstance, self).create(vals)
        if not self.env.context.get('syncing_instance'):
            instance.action_set_webhook()
        return instance

    def unlink(self):
        for instance in self:
            _logger.info("Excluindo a instância '%s' na Evolution API...", instance.name)
            try:
                self.env['whatsapp.evolution.api']._api_delete_instance(instance)
                _logger.info("Instância '%s' excluída com sucesso da Evolution API.", instance.name)
            except UserError as e:
                if '404' in str(e) or 'already in use' in str(e) or 'Forbidden' in str(e):
                    _logger.warning("A instância '%s' não foi encontrada ou já foi removida da API. Continuando com a exclusão no Odoo.", instance.name)
                else:
                    _logger.error("Falha ao excluir a instância '%s' na Evolution API: %s", instance.name, e)
                    raise UserError(_("Não foi possível excluir a instância na Evolution API. A exclusão foi cancelada. Erro: %s") % e)
         
        return super(WhatsappInstance, self).unlink()

    def action_delete_instance(self):
        self.unlink()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_set_webhook(self):
        for instance in self:
            if not instance.api_key:
                _logger.warning("Não é possível configurar o webhook para a instância '%s' sem uma Chave de API.", instance.name)
                continue
            
            correct_config = instance._get_correct_webhook_config()
            if not correct_config:
                continue

            try:
                _logger.info("Verificando e configurando o webhook para a instância '%s'...", instance.name)
                self.env['whatsapp.evolution.api']._api_set_webhook(instance, correct_config)
                webhook_url = correct_config.get('webhook', {}).get('url', 'URL não encontrada')
                _logger.info("Webhook para a instância '%s' configurado com sucesso para a URL: %s", instance.name, webhook_url)
                
            except UserError as e:
                _logger.warning("Falha ao configurar o webhook para a instância '%s'. O recebimento de mensagens pode não funcionar. Erro: %s", instance.name, e)

    def _get_api_config(self):
        # Este método agora pode ser chamado em um recordset vazio ou com um registro
        api_config = self.env['evolution.api.config']._get_config_record()
        if not api_config or not api_config.evolution_api_url or not api_config.evolution_api_global_key:
            raise UserError(_("A URL e a Chave Global da API devem ser configuradas."))
        return api_config.evolution_api_url, api_config.evolution_api_global_key

    def _update_details_from_api(self, instance_data):
        self.ensure_one()
        instance_details = instance_data
        if not instance_details: return 'disconnected'

        api_status = instance_details.get('connectionStatus')
        status = 'disconnected'
        if api_status == 'open':
            status = 'connected'
        elif api_status in ('connecting', 'pair_device', 'qrcode'):
            status = 'connecting'
             
        owner_jid = instance_details.get('ownerJid')
        phone_number = owner_jid.split('@')[0] if owner_jid else False
        count_data = instance_details.get('_count', {})
        vals = {
            'status': status,
            'profile_name': instance_details.get('profileName'),
            'phone_number': phone_number,
            'api_key': instance_details.get('token'),
            'contact_count': count_data.get('Contact', 0),
            'chat_count': count_data.get('Chat', 0),
            'message_count': count_data.get('Message', 0),
            'qrcode_image': False,
        }
         
        profile_pic_url = instance_details.get('profilePicUrl')
        if profile_pic_url:
            try:
                response = requests.get(profile_pic_url, timeout=10)
                if response.status_code == 200:
                    vals['profile_picture'] = base64.b64encode(response.content)
            except Exception as e:
                _logger.warning("Não foi possível buscar a foto do perfil para %s: %s", self.name, e)
        else:
            vals['profile_picture'] = False
         
        vals_to_write = {k: v for k, v in vals.items() if v is not None}
        self.write(vals_to_write)
        return status

    def action_connect_instance(self):
        self.ensure_one()
        self.action_set_webhook()
        
        try:
            self.write({'status': 'connecting', 'qrcode_image': False})
            api_response = self.env['whatsapp.evolution.api']._api_get_instance_connect(self)
            qrcode_base64 = api_response.get('base64') or api_response.get('code')
            if qrcode_base64:
                if ',' in qrcode_base64:
                    qrcode_base64 = qrcode_base64.split(',')[1]
                self.qrcode_image = qrcode_base64
            else:
                self.write({'status': 'error'})
                _logger.error("API não retornou um QR Code válido para a instância %s. Resposta: %s", self.name, api_response)
                raise UserError(_("Falha ao gerar QR Code. A API não retornou uma imagem válida. Verifique os logs do Odoo e da Evolution API."))
        except UserError as e:
            self.write({'status': 'error'})
            raise e
        except Exception as e:
            self.write({'status': 'error'})
            _logger.error("Erro ao gerar QR Code para %s: %s", self.name, e, exc_info=True)
            raise UserError(_("Ocorreu um erro inesperado ao tentar gerar o QR Code: %s") % e)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_disconnect_instance(self):
        self.ensure_one()
        try:
            self.env['whatsapp.evolution.api']._api_logout_instance(self)
            self.write({
                'status': 'disconnected',
                'profile_name': False,
                'phone_number': False,
                'profile_picture': False,
            })
        except Exception as e:
            _logger.error("Erro ao desconectar instância %s: %s", self.name, e)
            self.write({'status': 'disconnected'})
            raise UserError(_("Erro ao desconectar: %s") % str(e))

    def action_restart_instance(self):
        self.ensure_one()
        try:
            self.env['whatsapp.evolution.api']._api_restart_instance(self)
        except Exception as e:
            _logger.error("Erro ao reiniciar instância %s: %s", self.name, e)
            raise UserError(_("Erro ao reiniciar: %s") % str(e))
        return self.action_refresh_status()

    def action_refresh_status(self):
        instances_to_refresh = self or self.search([])
        try:
            base_url, api_key = self._get_api_config()
            all_instances_data = self.env['whatsapp.evolution.api']._send_api_request_global(
                base_url, api_key, 'GET', '/instance/fetchInstances'
            )
            api_instances_map = {inst.get('name'): inst for inst in all_instances_data if inst.get('name')}
            
            for instance in instances_to_refresh:
                if instance.name in api_instances_map:
                    new_status = instance._update_details_from_api(api_instances_map[instance.name])
                    if new_status == 'connecting':
                        _logger.info("Instância %s está 'Conectando'. Buscando novo QR Code.", instance.name)
                        try:
                            instance.action_connect_instance()
                        except Exception as e:
                            _logger.error("Falha ao buscar novo QR Code para %s durante a atualização: %s", instance.name, e)
                            instance.write({'status': 'error'})
                else:
                    instance.write({'status': 'disconnected'})

            return {'type': 'ir.actions.client', 'tag': 'reload'}
            
        except Exception as e:
            _logger.error("Falha ao atualizar status das instâncias: %s", e, exc_info=True)
            raise UserError(_("Falha ao comunicar com a API Evolution: %s") % e)

    @api.model
    def action_sync_instances(self):
        _logger.info("Iniciando sincronização de instâncias da Evolution API.")
        try:
            api_config = self.env['evolution.api.config']._get_config_record()
            base_url = api_config.evolution_api_url
            api_key = api_config.evolution_api_global_key
            if not base_url or not api_key:
                 raise UserError(_("A URL e a Chave Global da API devem ser configuradas."))

            api_instances_data = self.env['whatsapp.evolution.api']._send_api_request_global(
                base_url, api_key, 'GET', '/instance/fetchInstances'
            )
        except Exception as e:
            raise UserError(_("Não foi possível buscar as instâncias da Evolution API: %s") % e)
        
        api_instance_map = {inst.get('name'): inst for inst in api_instances_data if inst.get('name')}

        api_instance_names = set(api_instance_map.keys())
        odoo_instances = self.search([])
        odoo_instance_names = set(odoo_instances.mapped('name'))

        names_to_delete = odoo_instance_names - api_instance_names
        names_to_create = api_instance_names - odoo_instance_names
        names_to_update = odoo_instance_names.intersection(api_instance_names)

        if names_to_delete:
            instances_to_delete = self.search([('name', 'in', list(names_to_delete))])
            _logger.info("Excluindo %d instâncias fantasmas do Odoo: %s", len(instances_to_delete), list(names_to_delete))
            instances_to_delete.unlink()

        for name in names_to_create:
             instance_data = api_instance_map.get(name)
             if instance_data:
                vals = {'name': name}
                new_instance = self.with_context(syncing_instance=True).create(vals)
                new_instance._update_details_from_api(instance_data)

        instances_to_update = self.search([('name', 'in', list(names_to_update))])
        if instances_to_update:
            for instance in instances_to_update:
                if instance.name in api_instance_map:
                    instance._update_details_from_api(api_instance_map[instance.name])
        
        message_parts = []
        if names_to_delete:
            message_parts.append(_("%d instâncias foram excluídas.") % len(names_to_delete))
        if names_to_create:
            message_parts.append(_("%d novas instâncias foram importadas.") % len(names_to_create))
        if instances_to_update:
            message_parts.append(_("%d instâncias existentes foram atualizadas.") % len(instances_to_update))
        
        if not message_parts:
            message = _("Sincronização concluída. Nenhuma alteração detectada.")
        else:
            message = " ".join(message_parts)
            
        _logger.info("Verificando e configurando webhooks para todas as instâncias sincronizadas...")
        all_odoo_instances = self.search([('name', 'in', list(api_instance_names))])
        all_odoo_instances.action_set_webhook()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Sincronização Concluída"), 'message': message, 'type': 'success',
                'sticky': False, 'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    # ======================= INÍCIO DA ADIÇÃO (MÉTODO) =======================
    @api.model
    def _get_verifying_instance(self):
        """
        Encontra a melhor instância disponível para realizar uma verificação de número.
        Prioridade:
        1. Instância do tipo 'user' conectada e pertencente ao usuário atual.
        2. Qualquer instância do tipo 'company' conectada.
        Retorna um recordset de instância ou um recordset vazio.
        """
        # 1. Tenta encontrar uma instância pessoal do usuário logado
        user_instance = self.search([
            ('user_id', '=', self.env.uid),
            ('status', '=', 'connected'),
            ('instance_type', '=', 'user')
        ], limit=1)
        if user_instance:
            return user_instance

        # 2. Se não encontrar, busca uma instância de empresa conectada
        company_instance = self.search([
            ('instance_type', '=', 'company'),
            ('status', '=', 'connected')
        ], limit=1)
        
        return company_instance
    # ======================== FIM DA ADIÇÃO (MÉTODO) =========================

    def action_sync_with_odoo_user(self):
        """
        Sincroniza os dados da instância (nome do perfil, número e foto)
        com o registro do usuário responsável no Odoo.
        O fluxo é: Instância -> Usuário do Odoo.
        """
        self.ensure_one()
        if not self.user_id:
            raise UserError(_("Nenhum Usuário Responsável foi definido para esta instância."))

        if self.status != 'connected':
            raise UserError(_("A instância precisa estar conectada para que os dados de perfil estejam disponíveis para sincronização."))

        vals_to_write = {}
        if self.profile_name:
            vals_to_write['name'] = self.profile_name
        if self.phone_number:
            # O campo 'mobile' em res.users é o mais apropriado para o número do WhatsApp.
            vals_to_write['mobile'] = self.phone_number
        if self.profile_picture:
            # O campo de imagem em res.users é 'image_1920'.
            vals_to_write['image_1920'] = self.profile_picture

        if not vals_to_write:
            raise UserError(_("Não há dados (nome, celular ou foto) nesta instância para sincronizar. Tente atualizar o status primeiro."))

        self.user_id.write(vals_to_write)
        _logger.info("Dados da instância '%s' sincronizados para o usuário '%s'.", self.name, self.user_id.name)

        # Adiciona uma nota no chatter da instância para fins de auditoria.
        self.message_post(body=_("Os dados da instância (Nome, Celular, Foto) foram sincronizados com o usuário do Odoo '%s'.") % self.user_id.name)

        # Retorna uma notificação para o usuário.
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Sincronização Concluída"),
                'message': _("Os dados do usuário %s foram atualizados com sucesso.") % self.user_id.name,
                'type': 'success',
                'sticky': False,
            }
        }
    # ======================== FIM DA ADIÇÃO (MÉTODO) =========================