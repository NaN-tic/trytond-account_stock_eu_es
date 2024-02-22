# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    intrastat_cancelled = fields.Boolean("Intrastat Cancelled")

    @staticmethod
    def default_intrastat_cancelled():
        return False

    @classmethod
    def _update_intrastat(cls, moves):
        if not Transaction().context.get('_update_intrastat_declaration'):
            super()._update_intrastat(moves)

    def _set_intrastat(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')
        PurchaseLine = pool.get('purchase.line')

        super()._set_intrastat()

        if not self.intrastat_type:
            return
        # Some times is possible that user change or remove the tariff_code in
        # some products after some moves of this productes are done. So, when
        # update some moves Intrastat values is need to reset the tariff_code.
        if Transaction().context.get('_update_intrastat_declaration'):
            intrastat_tariff_code = self.product.get_tariff_code(
                self._intrastat_tariff_code_pattern())
            if not intrastat_tariff_code:
                intrastat_tariff_code = self.product.get_tariff_code(
                    self._intrastat_tariff_code_pattern_wo_country())
            if intrastat_tariff_code != self.intrastat_tariff_code:
                self.intrastat_tariff_code = intrastat_tariff_code
        elif not self.intrastat_tariff_code:
            self.intrastat_tariff_code = self.product.get_tariff_code(
                self._intrastat_tariff_code_pattern_wo_country())
        if (not self.intrastat_additional_unit
                and self.intrastat_tariff_code
                and self.intrastat_tariff_code.intrastat_uom):
            quantity = self._intrastat_quantity(
                self.intrastat_tariff_code.intrastat_uom)
            if quantity is not None:
                ndigits = self.__class__.intrastat_additional_unit.digits[1]
                self.intrastat_additional_unit = round(quantity, ndigits)

        if (not self.intrastat_transport
                and self.shipment and self.shipment.intrastat_transport):
            self.intrastat_transport = self.shipment.intrastat_transport

        if not self.intrastat_incoterm:
            if self.origin:
                if isinstance(self.origin, SaleLine):
                    self.intrastat_incoterm = self.origin.sale.incoterm or None
                elif isinstance(self.origin, PurchaseLine):
                    self.intrastat_incoterm = (self.origin.purchase.incoterm
                        or None)

    def _intrastat_tariff_code_pattern_wo_country(self):
        return {
            'date': self.effective_date,
            }

    def _intrastat_value(self):
        pool = Pool()
        Move = pool.get('stock.move')
        Currency = pool.get('currency.currency')

        intrastat_value_from_invoice = Decimal('0.0')
        invoices = [l.invoice for l in self.invoice_lines
            if l.invoice and l.invoice.state in ('posted', 'paid')]
        # TODO: Control correctly UoM
        quantity = sum(l.quantity for l in self.invoice_lines if l.quantity > 0)
        intrastat_value = super()._intrastat_value()
        if invoices and quantity == self.quantity:
            intrastat_value_from_invoice = Move._intrastat_value_from_invoices(
                self, invoices, intrastat_value)
            ndigits = Move.intrastat_value.digits[1]
            with Transaction().set_context(
                    date=self.effective_date or self.planned_date):
                intrastat_value_from_invoice = round(Currency.compute(
                        self.currency,
                        intrastat_value_from_invoice,
                        self.company.intrastat_currency,
                        round=False), ndigits)

        return intrastat_value_from_invoice or intrastat_value

    @classmethod
    def _intrastat_value_from_invoices(cls, move, invoices, intrastat_value):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')

        lines_discounts = Invoice.get_invoice_intrastat_discount_per_line(
            invoices)

        value = 0
        for line, amount in lines_discounts.items():
            if move not in line.stock_moves:
                continue
            # Ensure that cache only take this 'line' an not 1.000
            # registers. Beacsue in some cases the line may don't have and
            # ivoice assocaited yet and it's needed for the company_amount
            # field calculation.
            line = InvoiceLine(line)
            invoice_date = (line.invoice.accounting_date
                or line.invoice.invoice_date)
            invoice_date = invoice_date.replace(day=1)

            move_date = move.effective_date or move.planned_date
            move_date = move_date.replace(day=1)
            if move_date != invoice_date:
                continue
            # Amount arrive with the sign setted in the line.
            value += amount
        return value

    def _intrastat_quantity(self, uom):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        result = super()._intrastat_quantity(uom)
        if not result:
            m = UoM(ModelData.get_id('product', 'uom_meter'))
            if (self.product.width
                    and self.product.width_uom.category == self.unit.category
                    and self.unit.category == m.category):
                width_meter = UoM.compute_qty(
                    self.product.width_uom,
                    self.product.width,
                    m, round=False)
                internal_quantity_meter = UoM.compute_qty(
                    self.unit,
                    self.internal_quantity,
                    m, round=False)
                return width_meter * internal_quantity_meter
        return result

    @classmethod
    def update_intrastat_declaration(cls, moves):
        with Transaction().set_context(_update_intrastat_declaration=True):
            for move in moves:
                move.intrastat_type = move.on_change_with_intrastat_type()
                move._set_intrastat()
                if not move.internal_weight:
                    internal_weight = cls._get_internal_weight(
                        move.quantity, move.unit, move.product)
                    move.internal_weight = internal_weight or 0
            cls.save(moves)

    @classmethod
    def copy(cls, moves, default=None):
        default = default.copy() if default else {}
        default.setdefault('intrastat_cancelled')
        return super().copy(moves, default=default)


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

    @fields.depends('carrier')
    def on_change_carrier(self):
        try:
            super().on_change_carrier()
        except AttributeError:
            pass
        if self.carrier:
            self.intrastat_transport = self.carrier.intrastat_transport


class ShipmentInternal(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'


class ShipmentInReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class ShipmentOutReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'
