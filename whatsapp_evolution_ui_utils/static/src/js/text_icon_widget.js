/** @odoo-module **/

import { registry } from '@web/core/registry';
import { usePopover } from "@web/core/popover/popover_hook";
import { standardFieldProps } from '@web/views/fields/standard_field_props';
import { Component, useRef } from '@odoo/owl';
import { Tooltip } from "@web/core/tooltip/tooltip";

export class TextIconWidget extends Component {
    static template = 'whatsapp_evolution_ui_utils.TextIconWidget';
    static props = {
        ...standardFieldProps,
        icon: { type: String, optional: true },
    };
    static defaultProps = {
        icon: 'comment',
    };

    setup() {
        this.iconRef = useRef('icon');
        this.popover = usePopover(Tooltip);
    }

    get hasValue() {
        const value = this.props.record.data[this.props.name];
        return value && value.trim() !== '';
    }

    showTooltip(ev) {
        if (!this.hasValue) return;
        this.popover.open(this.iconRef.el, {
            template: 'whatsapp_evolution_ui_utils.TextValueTooltip',
            info: {
                value: this.props.record.data[this.props.name]
            }
        });
    }
}

export const textIconWidget = {
    component: TextIconWidget,
    supportedTypes: ['html', 'text'],
    supportedOptions: [
        { label: 'Icon', name: 'icon', type: 'string' }
    ],
    extractProps: ({ options }) => ({
        icon: options.icon,
    }),
};

registry.category('fields').add('text_icon', textIconWidget);