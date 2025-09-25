/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class WhatsappListMediaWidget extends Component {
    static template = "whatsapp_evolution_base.WhatsappListMediaWidget";
    static props = {
        ...standardFieldProps,
    };

    /**
     * Gera um texto amigável para anexos de mídia, usando a extensão do arquivo
     * quando disponível para fornecer mais detalhes.
     */
    get friendlyMediaText() {
        const mediaType = this.props.record.data.media_type;
        const filename = this.props.record.data.media_filename || '';
        const extension = (filename.split('.').pop() || '').toUpperCase();

        switch (mediaType) {
            case 'image': return "Anexo de Imagem";
            case 'video': return "Anexo de Vídeo";
            case 'sticker': return "Sticker";
            case 'document':
                // Adiciona a extensão ao documento se ela existir
                return extension ? `Anexo: Documento (${extension})` : "Anexo: Documento";
            case 'audio':
                // Este texto é um fallback, pois o template tentará renderizar o player primeiro.
                return "Anexo de Áudio";
            default:
                // Fallback para qualquer outro tipo de mídia não mapeado.
                return filename || "Anexo de Mídia";
        }
    }
}

registry.category("fields").add("whatsapp_list_media_widget", {
    component: WhatsappListMediaWidget,
    supportedTypes: ["text"], // O widget é aplicado em um campo de texto ('body')
});