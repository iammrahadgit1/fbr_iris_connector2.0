import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    setup(data, options) {
        super.setup(data, options);
        this.fbr_invoice_number = data.fbr_invoice_number || "";
    },

    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.fbr_invoice_number = this.fbr_invoice_number;

        // Add partner (customer) data
        if (this.get_partner()) {
            result.partner = {
                id: this.get_partner().id,
                name: this.get_partner().name,
                phone: this.get_partner().phone,
                vat: this.get_partner().vat,
            };
        }

        return result;
    },
});

patch(PosOrderline.prototype, {
    getDisplayData() {
        const result = super.getDisplayData();
        const prices = this.get_all_prices();
        const tax_amount = prices.priceWithTax - prices.priceWithoutTax;
        const tax_percent =
            prices.priceWithTax && prices.priceWithoutTax
                ? (tax_amount / prices.priceWithoutTax) * 100
                : 0;

        const serviceFeeProductId = this.config.pos_service_fee_product_id;
        const is_service_charge = !!(
            serviceFeeProductId && 
            this.product && 
            this.product.id === serviceFeeProductId
        );

        return {
            ...result,
            product_id: this.get_product()?.id || null,
            price_subtotal: this.get_base_price(),
            price_with_tax: prices.priceWithTax,
            tax_amount: tax_amount,
            tax_percent: tax_percent,
            is_service_charge: is_service_charge,
            skip_receipt: is_service_charge,
            taxes: this.tax_ids?.map(tax => ({
                id: tax.id,
                name: tax.name,
                amount: tax.amount,
                amount_type: tax.amount_type  // <-- Added
            })) || []
        };
    },
});


patch(Orderline, {
    props: {
        ...Orderline.props,
        line: {
            ...Orderline.props.line,
            shape: {
                ...Orderline.props.line.shape,
                product_id: { type: Number, optional: true },
                price_subtotal: { type: Number, optional: true },
                price_with_tax: { type: Number, optional: true },
                tax_amount: { type: Number, optional: true },
                tax_percent: { type: Number, optional: true },
                taxes: { type: Array, optional: true }

            },
        },
    },
});
