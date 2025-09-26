/** @odoo-module **/

import { ChannelSelector } from "@mail/discuss/core/web/channel_selector";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

patch(ChannelSelector.prototype, {

    async fetchSuggestions() {
        if (this.props.category.id === "whatsapp") {
            // Search for res.partner instead of discuss.channel
            const partners = await this.orm.searchRead(
                "res.partner",
                [
                    ["mobile", "!=", false],
                    "|",
                    ["name", "ilike", this.state.value],
                    ["mobile", "ilike", this.state.value],
                ],
                ["display_name", "mobile"],
                { limit: 10 }
            );

            this.state.navigableListProps.options = partners.map((partner) => ({
                id: partner.id,
                label: partner.display_name,
                description: partner.mobile,
                classList: "o-mail-ChannelSelector-suggestion",
            }));

            if (partners.length === 0) {
                this.state.navigableListProps.options.push({
                    label: _t("No contacts found."),
                    unselectable: true,
                });
            }
            return;
        }
        return super.fetchSuggestions(...arguments);
    },

    async onSelect(option) {
        if (this.props.category.id === "whatsapp") {
            try {
                // Call a new Python method to get or create the channel
                const channel_data = await this.orm.call(
                    "discuss.channel",
                    "get_or_create_whatsapp_channel_for_partner",
                    [option.id]
                );
                
                // Odoo 17+: use the store to handle data insertion
                this.store.insert(channel_data);
                const thread = this.store.Thread.get(channel_data.id);
                if (thread) {
                    thread.open();
                }

            } catch (e) {
                this.env.services.notification.add(_t("Could not start conversation. Make sure a connected WhatsApp instance is available."), { type: "danger" });
            }
            this.onValidate(); // Close the selector
            return;
        }
        return super.onSelect(option);
    },
});