# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @fields.depends('intrastat_tariff_code')
    def on_change_with_intrastat_tariff_code_uom(self, name=None):
        if (self.intrastat_tariff_code
                and self.intrastat_tariff_code.intrastat_uom):
            return self.intrastat_tariff_code.intrastat_uom.id

    def _set_intrastat(self):
        pool = Pool()
        Country = pool.get('country.country')
        super()._set_intrastat()

        country_of_origin_code = ('PT' if self.product
            and self.product.producible
            and (self.product.account_category.id == 11
                or (self.product.account_category.parent
                    and self.product.account_category.parent.id == 11))
            else ('ES' if self.product and self.product.producible
                else (self.product.product_suppliers[0].party.addresses[0].
                      country.code if self.product 
                      and self.product.product_suppliers 
                      and self.product.product_suppliers[0].party 
                      and self.product.product_suppliers[0].party.addresses 
                      else 'ES')))
        country_of_origins = Country.search([
                ('code', '=', country_of_origin_code)
                ], limit=1)
        if country_of_origins:
            self.intrastat_country_of_origin = country_of_origins[0]

        # if self.intrastat_type == 'arrival':
        #     pass
        # elif self.intrastat_type == 'dispatch':
        #     pass
        #     #self.intrastat_country_of_origin = (self.shipment
        #     #    and self.shipment.delivery_address
        #     #    and self.shipment.delivery_address.country
        #     #    or None)

        if not self.intrastat_tariff_code:
            self.intrastat_tariff_code = self.product.get_tariff_code(
                self._intrastat_tariff_code_pattern_wo_country())

        if self.shipment and self.shipment.intrastat_transport:
            self.intrastat_transport = self.shipment.intrastat_transport

    def _intrastat_tariff_code_pattern_wo_country(self):
        return {
            'date': self.effective_date,
            }

    def _intrastat_quantity(self, uom):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        result = super()._intrastat_quantity(uom)
        if not result:
            m = UoM(ModelData.get_id('product', 'uom_meter'))
            if (self.product.width
                    and self.product.width_uom.category == self.uom.category
                    and self.uom.category == m.category):
                width_meter = UoM.compute_qty(
                    self.product.width_uom,
                    self.product.width,
                    m, round=False)
                internal_quantity_meter = UoM.compute_qty(
                    self.uom,
                    self.internal_quantity,
                    m, round=False)
                return width_meter * internal_quantity_meter
        return result

    # TODO: Intrastat, check how is set the destination country (firs colum in
    # file)
    #o.shipment and hasattr(o.shipment, 'delivery_address') and o.shipment.delivery_address.country and o.shipment.delivery_address.country.name or '(Vacío)'

    # TODO: Intrastat, check how VAT is get
    #o.shipment and hasattr(o.shipment, 'delivery_address') and o.shipment.delivery_address.party and o.shipment.delivery_address.party.tax_identifier and o.shipment.delivery_address.party.tax_identifier.code or '(Vacío)'


class Move_Incoterm(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def _set_intrastat(self):
        super()._set_intrastat()

        if (not self.intrastat_transport
                and self.shipment.intrastat_transport):
            self.intrastat_transport = self.shipment.intrastat_transport


class ShipmentMixin:
    __slots__ = ()

    intrastat_transport = fields.Many2One(
        'account.stock.eu.intrastat.transport', "Intrastat Transport",
        ondelete='RESTRICT')


class ShipmentIn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @fields.depends('contact_address')
    def on_change_contact_address(self):
        if self.contact_address:
            self.intrastat_from_country = self.contact_address.country


class ShipmentOut(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    def on_change_carrier(self):
        try:
            super().on_change_carrier()
        except AttributeError:
            pass
        self.intrastat_transport = self.carrier.intrastat_transport
