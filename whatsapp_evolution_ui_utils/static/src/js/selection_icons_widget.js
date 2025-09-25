/** @odoo-module **/

import { registry } from '@web/core/registry';
import { SelectionField, selectionField } from '@web/views/fields/selection/selection_field';

export class SelectionIconsWidget extends SelectionField {
    static template = 'whatsapp_evolution_ui_utils.SelectionIconsWidget';
    static props = {
        ...SelectionField.props,
        icons: { type: Object },
    };

    get valueIcon() {
        const value = this.props.record.data[this.props.name];
        return this.props.icons && this.props.icons[value] || '';
    }

    // =================== INÍCIO DA CORREÇÃO ===================
    get valueString() {
        // ADICIONADO: Verificação de segurança para garantir que props.selection existe e é um array.
        if (!this.props.selection || !Array.isArray(this.props.selection)) {
            return ''; // Retorna uma string vazia se as opções não estiverem disponíveis.
        }
        const value = this.props.record.data[this.props.name];
        const selection = this.props.selection.find(s => s[0] === value);
        return selection ? selection[1] : '';
    }
    // ==================== FIM DA CORREÇÃO =====================
}

export const selectionIconsWidget = {
    ...selectionField,
    component: SelectionIconsWidget,
    supportedTypes: ['selection'],
    supportedOptions: [
        {
            label: 'Icons',
            name: 'icons',
            type: 'string',
        },
    ],
    extractProps({ attrs, options }) {
        const props = selectionField.extractProps(...arguments);
        props.icons = options.icons;
        return props;
    },
};

registry.category('fields').add('selection_icons', selectionIconsWidget);