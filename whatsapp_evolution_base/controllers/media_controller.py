# -*- coding: utf-8 -*-
import requests
import os
import mimetypes
from urllib.parse import urlparse

from odoo import http
from odoo.http import request

import logging
_logger = logging.getLogger(__name__)

class MediaProxyController(http.Controller):

    @http.route('/whatsapp/media/download/<int:message_id>', type='http', auth="user", methods=['GET'])
    def download_media(self, message_id, **kw):
        """
        Atua como um proxy para baixar mídias de URLs externas, garantindo os headers corretos.
        Isso resolve o problema de arquivos serem baixados como '.bin'.
        """
        media_url = None
        try:
            message = request.env['whatsapp.message'].sudo().browse(message_id)
            if not message or not message.media_url:
                _logger.warning("Download de mídia: Mensagem ou URL não encontrada para o ID: %s", message_id)
                return request.notfound("Mídia não encontrada.")

            media_url = message.media_url
            
            # Faz a requisição para a URL externa, com streaming para eficiência
            external_response = requests.get(media_url, stream=True, timeout=30)
            external_response.raise_for_status()  # Lança exceção para erros HTTP (4xx, 5xx)

            # Determina o Content-Type (tipo do arquivo)
            content_type = external_response.headers.get('Content-Type', 'application/octet-stream')

            # Determina o nome do arquivo (fallback para o nome salvo no Odoo)
            filename = message.media_filename
            if not filename:
                # Se não houver nome, tenta extrair da URL
                parsed_url = urlparse(media_url)
                filename = os.path.basename(parsed_url.path) or f"download.{mimetypes.guess_extension(content_type) or 'bin'}"
            
            # Monta o header Content-Disposition
            disposition = f'attachment; filename="{filename}"'

            headers = [
                ('Content-Type', content_type),
                ('Content-Disposition', disposition),
            ]
            
            # Retorna a resposta do Odoo, transmitindo o conteúdo em blocos (stream)
            response = request.make_response(external_response.iter_content(chunk_size=1024), headers)
            return response

        except requests.exceptions.RequestException as e:
            _logger.error("Falha ao baixar mídia de %s: %s", media_url, e)
            return request.notfound(f"Não foi possível buscar a mídia externa. Erro: {e}")
        except Exception as e:
            _logger.exception("Erro inesperado no download de mídia para o ID %s: %s", message_id, e)
            return request.make_response("Erro interno no servidor ao processar o download.", status=500)