# -*- coding: utf-8 -*-
import json
import logging
import mimetypes
from odoo import http
from odoo.http import request
from datetime import datetime

_logger = logging.getLogger(__name__)

class WhatsappWebhookController(http.Controller):

    @http.route('/whatsapp/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def receive_webhook(self):
        try:
            payload = request.get_json_data()
            _logger.info("Webhook recebido: %s", json.dumps(payload, indent=2, ensure_ascii=False))
            
            instance_name = payload.get('instance')
            instance = request.env['whatsapp.instance'].sudo().search([('name', '=', instance_name)], limit=1)
            if not instance:
                _logger.warning(f"Webhook ignorado: Instância '{instance_name}' não encontrada.")
                return {'status': 'ok', 'message': f'Instance {instance_name} not found'}

            event = payload.get('event')
            
            # ======================= INÍCIO DA MODIFICAÇÃO ======================= 
            # Adicionamos um contexto para passar a mensagem completa para a camada do Discuss. 
            # Esta é a chave para permitir que o módulo `whatsapp_evolution_discuss` processe as mídias. 
            if event == 'messages.upsert': 
                message_data = payload.get('data', {}) 
                request.update_context(webhook_message_data=message_data) 
            # ======================== FIM DA MODIFICAÇÃO ========================= 
            
            if event == 'messages.upsert': 
                message_data = payload.get('data', {}) 
                key = message_data.get('key', {}) 
                message_content = message_data.get('message', {})
                
                if not message_content or not key.get('id'):
                    return {'status': 'ok', 'message': 'Skipped, no message content or key ID'}

                timestamp = message_data.get('messageTimestamp')
                if not timestamp:
                    return {'status': 'ok', 'message': 'Skipped, no timestamp'}

                if request.env['whatsapp.message'].sudo().search_count([('message_id', '=', key.get('id'))]):
                    _logger.info("Webhook ignorado: Mensagem com ID '%s' já existe.", key.get('id'))
                    return {'status': 'ok', 'message': 'Message already exists'}

                is_group = '@g.us' in (key.get('remoteJid') or '')
                sender_jid = key.get('participant') if is_group and not key.get('fromMe') else key.get('remoteJid')
                
                vals = {
                    'instance_id': instance.id,
                    'message_id': key.get('id'),
                    'timestamp': datetime.fromtimestamp(int(timestamp)),
                    'message_direction': 'inbound' if not key.get('fromMe') else 'outbound',
                    'raw_json': json.dumps(payload),
                    'state': 'delivered' if not key.get('fromMe') else 'sent',
                    'is_group': is_group,
                    'sender_name': message_data.get('pushName') or (sender_jid.split('@')[0] if sender_jid else 'Desconhecido'),
                    'phone_number': sender_jid.split('@')[0] if sender_jid else None,
                    'body': "",
                }
                
                # ======================= INÍCIO DA CORREÇÃO DE RESPOSTA =======================
                # Lógica de busca de contexto mais robusta
                context_info = message_content.get('contextInfo') or \
                               message_data.get('contextInfo') or \
                               message_content.get('extendedTextMessage', {}).get('contextInfo')

                if context_info:
                    quoted_msg_id_str = context_info.get('stanzaId')
                    if quoted_msg_id_str:
                        # Procura a mensagem original no nosso log
                        quoted_msg = request.env['whatsapp.message'].sudo().search(
                            [('message_id', '=', quoted_msg_id_str)], limit=1
                        )
                        if quoted_msg:
                            vals['quoted_message_id'] = quoted_msg.id
                # ======================== FIM DA CORREÇÃO DE RESPOSTA =========================
                
                # --- INÍCIO DA CORREÇÃO 1: Detecção de Tipo de Mensagem Aprimorada ---
                # Lista de prioridade para garantir que peguemos o conteúdo real, não mensagens técnicas.
                priority_message_types = [
                    'conversation', 'extendedTextMessage', 'reactionMessage', 'imageMessage',
                    'videoMessage', 'stickerMessage', 'audioMessage', 'documentMessage'
                ]
                message_type_key = None
                for msg_type in priority_message_types:
                    if msg_type in message_content:
                        message_type_key = msg_type
                        break
                
                # Se não encontrarmos um tipo prioritário, pegamos o primeiro que não seja de contexto.
                if not message_type_key:
                    message_type_key = next((k for k in message_content if k != 'messageContextInfo'), None)
                # --- FIM DA CORREÇÃO 1 ---

                vals['message_type'] = message_type_key

                if not message_type_key:
                    _logger.warning("Não foi possível determinar um tipo de mensagem válido para o payload: %s", message_content)
                    return {'status': 'ok', 'message': 'Could not determine a valid message type'}

                if message_type_key in ['conversation', 'extendedTextMessage']:
                    vals['body'] = message_content.get('conversation') or \
                                   message_content.get('extendedTextMessage', {}).get('text', '')
                elif message_type_key == 'reactionMessage':
                    reaction = message_content.get('reactionMessage', {})
                    emoji = reaction.get('text', '')
                    vals['body'] = f"Reagiu com: {emoji}" if emoji else "Reação removida"
                    reacted_msg_id = reaction.get('key', {}).get('id')
                    if reacted_msg_id:
                        reacted_msg = request.env['whatsapp.message'].sudo().search([('message_id', '=', reacted_msg_id)], limit=1)
                        if reacted_msg: vals['reacted_message_id'] = reacted_msg.id
                elif message_type_key in ['imageMessage', 'videoMessage', 'stickerMessage', 'audioMessage', 'documentMessage']:
                    media_map = {
                        'imageMessage': 'image', 'videoMessage': 'video', 'stickerMessage': 'sticker',
                        'audioMessage': 'audio', 'documentMessage': 'document',
                    }
                    vals['media_type'] = media_map.get(message_type_key, 'other')
                    
                    media_info = message_content.get(message_type_key, {})
                    
                    raw_url = message_content.get('mediaUrl') or media_info.get('url')
                    # --- INÍCIO DA CORREÇÃO 2: Limpeza da URL ---
                    if raw_url:
                        vals['media_url'] = raw_url.split('?')[0]
                    # --- FIM DA CORREÇÃO 2 ---
                    
                    vals['body'] = media_info.get('caption', '')
                    vals['media_filename'] = media_info.get('fileName') or media_info.get('title')
                    
                    if not vals.get('media_filename'):
                        mimetype = media_info.get('mimetype')
                        ext = mimetypes.guess_extension(mimetype.split(';')[0]) if mimetype else ''
                        vals['media_filename'] = f"{vals['media_type']}_{key.get('id')}{ext or '.bin'}"

                else:
                    # Ignora tipos de mensagem técnicos ou não suportados
                    _logger.info("Ignorando tipo de mensagem não processado: %s", message_type_key)
                    return {'status': 'ok', 'message': f'Skipped unsupported message type: {message_type_key}'}

                if vals.get('body') is None:
                    vals['body'] = ""
                
                # ==================== INÍCIO DA NOVA LÓGICA ====================
                # Verifica se a camada superior (contact_management) já identificou o parceiro
                webhook_partner_id = request.context.get('webhook_partner_id')
                if webhook_partner_id:
                    vals['partner_id'] = webhook_partner_id
                # ===================== FIM DA NOVA LÓGICA ======================

                request.env['whatsapp.message'].sudo().create(vals)
                _logger.info("Mensagem de '%s' (Tipo: %s) salva com sucesso.", vals['sender_name'], message_type_key)

            elif event == 'messages.update':
                updates = payload.get('data', [])
                if isinstance(updates, dict):
                    updates = [updates]

                for update_data in updates:
                    key_id = update_data.get('keyId')
                    status_str = update_data.get('status', '').lower()
                    
                    status_map = {
                        'delivered': 'delivered', 'read': 'read',
                        'error': 'failed', 'played': 'read',
                    }
                    new_status = status_map.get(status_str)
                    
                    if key_id and new_status:
                        message = request.env['whatsapp.message'].sudo().search([('message_id', '=', key_id)], limit=1)
                        if message and message.state != 'read':
                            message.write({'state': new_status})
                            _logger.info("Status da mensagem '%s' atualizado para '%s'.", key_id, new_status)

            elif event == 'connection.update':
                connection_data = payload.get('data', {})
                new_status = 'disconnected'
                if connection_data.get('state') == 'open':
                    new_status = 'connected'
                elif connection_data.get('state') == 'connecting':
                    new_status = 'connecting'
                instance.sudo().write({'status': new_status})

            return {'status': 'success', 'message': 'Webhook processed'}
        
        except Exception as e:
            _logger.error("Erro fatal ao processar webhook da Evolution API: %s", e, exc_info=True)
            return {'status': 'error', 'message': str(e)}