import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";
import { patch } from "@web/core/utils/patch";

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
                is_service_charge: { type: Boolean, optional: true },
                skip_receipt: { type: Boolean, optional: true },
            },
        },
    },
});