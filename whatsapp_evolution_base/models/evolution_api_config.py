import logging
from odoo import fields, models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EvolutionApiConfig(models.Model):
    _name = 'evolution.api.config'
    _description = 'Evolution API Configuration (Singleton)'
    
    # MUDANÇA: Adicionado o campo 'name' para ser o título do registro
    # Odoo usa este campo por padrão como o nome de exibição.
    name = fields.Char(
        string='Configuration Name',
        default='Evolution API Configuration',
        required=True,
        readonly=True
    )

    evolution_api_url = fields.Char(string="Evolution API URL", help="URL base do seu servidor Evolution API (ex: http://localhost:8080)")
    evolution_api_global_key = fields.Char(string="Evolution Global API Key", help="Chave de API global para gerenciar instâncias.")

    # ... o resto do seu código python permanece o mesmo ...
    def action_save(self):
        """
        Ação do botão 'Salvar'. O Odoo já salva o registro antes de chamar este método.
        Podemos adicionar validações ou lógicas extras aqui se necessário.
        """
        self.ensure_one()
        _logger.info("Configurações da Evolution API salvas.")
        # Opcional: retornar uma notificação para o usuário
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Salvo'),
                'message': _('As configurações da API Evolution foram salvas com sucesso.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_cancel(self):
        """
        Ação do botão 'Cancelar'. Simplesmente fecha a janela.
        O Odoo Web Client lida com o descarte de alterações não salvas.
        """
        # Esta ação pode ser manipulada diretamente pelo atributo special="cancel" no XML,
        # mas ter o método aqui permite mais flexibilidade se necessário.
        return {'type': 'ir.actions.act_window_close'}

    @api.model
    def _get_config_record(self):
        """
        Método auxiliar para encontrar ou criar o único registro de configuração.
        Isso é parte do padrão Singleton.
        """
        # Tenta encontrar o registro usando o XML ID que criaremos
        config_record = self.env.ref('whatsapp_evolution_base.evolution_api_config_singleton_record', raise_if_not_found=False)
        if not config_record:
            # Se não encontrar (ex: o registro de dados ainda não foi carregado), procura qualquer um
            config_record = self.search([], limit=1)
            if not config_record:
                # Se ainda não houver nenhum, cria um
                config_record = self.create({})
        return config_record

    # MUDANÇA 4: Sobrescrever métodos create e unlink para garantir que sempre exista apenas um registro
    @api.model
    def create(self, vals):
        if self.search_count([]) > 0:
            raise UserError(_('Já existe uma configuração da Evolution API. Você não pode criar uma nova.'))
        return super(EvolutionApiConfig, self).create(vals)

    def unlink(self):
        raise UserError(_('Você não pode apagar a configuração da Evolution API.'))