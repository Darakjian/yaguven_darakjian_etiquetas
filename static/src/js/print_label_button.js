/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const BRIDGE_URL = "http://localhost:9199/write";

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
            const response = await fetch(BRIDGE_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ data: zpl }),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            this.notification.add("Etiqueta enviada a la Zebra", {
                type: "success",
            });
        } catch (error) {
            this.notification.add("No se pudo imprimir: " + error.message, {
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
