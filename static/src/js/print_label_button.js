/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// 127.0.0.1 y NO "localhost": en macOS "localhost" resuelve primero a ::1 (IPv6) y el
// bridge escucha solo en IPv4 (`ZBRIDGE_LISTEN_HOST` por defecto en 127.0.0.1). Verificado
// en el iMac de la tienda: por 127.0.0.1 responde 200, por [::1] no responde nada. curl
// disimula el problema porque reintenta con IPv4; el navegador no siempre lo hace, y el
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
            const response = await fetch(BRIDGE_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ data: zpl }),
            });
            if (!response.ok) {
                throw new Error(await response.text());
            }
            this.notification.add(_t("Tag sent to the Zebra printer"), {
                type: "success",
            });
            // El registro en el chatter va DESPUES del OK del bridge: lo que queda
            // asentado es lo que efectivamente salio en papel, no cada intento. Y va
            // en su propio try: si el chatter falla, la etiqueta ya se imprimio igual
            // y decirle al usuario que no se imprimio seria mentirle.
            try {
                await this.orm.call(
                    "product.product",
                    "action_log_printed_label",
                    [[resId]]
                );
                // Refrescar es cosmetico (que el mensaje aparezca sin recargar a mano) y
                // la API de recarga cambia entre versiones: si falla, se traga el error.
                // El mensaje ya esta posteado; avisar de un problema aca seria confundir.
                try {
                    await this.props.record.load();
                } catch {
                    // no pasa nada: se ve al refrescar la ficha
                }
            } catch (error) {
                this.notification.add(
                    _t("Printed, but the preview could not be logged: %s", error.message),
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
