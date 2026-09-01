/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// 127.0.0.1 y NO "localhost": en macOS "localhost" resuelve primero a ::1 (IPv6) y el
// bridge only listens on IPv4 (`ZBRIDGE_LISTEN_HOST` defaults to 127.0.0.1). Verified on
// the store's iMac: 127.0.0.1 answers 200, [::1] answers nothing at all. curl hides the
// problem because it retries over IPv4; the browser does not always do that, and the
// sintoma es un "Failed to fetch" pelado que no dice de que se trata.
const BRIDGE_URL = "http://127.0.0.1:9199/write";

class PrintJewelryLabelButton extends Component {
    static template = "yaguven_darakjian_etiquetas.PrintLabelButton";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ printing: false });
    }

    async onClick() {
        const resId = this.props.record.resId;
        if (!resId) {
            return;
        }
        this.state.printing = true;
        try {
            const zpl = await this.orm.call(
                "product.product",
                "get_jewelry_label_zpl",
                [[resId]]
            );
            // The tag goes to the chatter whether or not the printer answers. Away from
            // the counter, or on a tablet, seeing what the tag would say is worth as much
            // as printing it -- and the chatter entry says which of the two happened.
            let impreso = false;
            let fallo = "";
            try {
                const response = await fetch(BRIDGE_URL, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ data: zpl }),
                });
                if (!response.ok) {
                    throw new Error(await response.text());
                }
                impreso = true;
            } catch (error) {
                fallo = error.message;
            }
            this.notification.add(
                impreso
                    ? _t("Tag sent to the Zebra printer")
                    : _t("The printer did not answer. The tag is in the chatter: %s", fallo),
                { type: impreso ? "success" : "warning" }
            );
            // The chatter entry sits in its own try: if it fails the tag may well have
            // been printed, and saying it was not would be a lie.
            try {
                await this.orm.call(
                    "product.product",
                    "action_log_printed_label",
                    [[resId], impreso]
                );
                // Refreshing is cosmetic - it just saves a manual reload to see the
                // message - and the reload API changes between versions, so a failure is
                // swallowed. The message is already posted; reporting a problem here
                // would only confuse.
                try {
                    await this.props.record.load();
                } catch {
                    // no harm done: it shows up on the next refresh of the form
                }
            } catch (error) {
                this.notification.add(
                    _t("The tag could not be logged in the chatter: %s", error.message),
                    { type: "warning" }
                );
            }
        } catch (error) {
            this.notification.add(_t("Could not print: %s", error.message), {
                type: "danger",
            });
        } finally {
            this.state.printing = false;
        }
    }
}

registry.category("view_widgets").add("print_jewelry_label", {
    component: PrintJewelryLabelButton,
});
