# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields, ModelSQL
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    intrastat_exempt_taxes = fields.Many2Many(
        'stock.configuration-account.tax', 'configuration', 'tax',
        "Intrastat Exempt Taxes")


class StockConfigurationAccountTax(ModelSQL):
    "Stock Configuration - Account Tax"
    __name__ = 'stock.configuration-account.tax'

    configuration = fields.Many2One(
        'stock.configuration', "Stock Configuration", ondelete='CASCADE',
        required=True)
    tax = fields.Many2One(
        'account.tax', "Tax", ondelete='CASCADE', required=True,
        domain=[
            ('parent', '=', None),
            ],
        )

class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    intrastat_cancelled = fields.Boolean("Intrastat Cancelled")
    shipment_price_list = fields.Function(fields.Many2One('product.price_list',
            "Price List"), 'get_shipment_price_list',
        searcher='search_shipment_price_list')

    @staticmethod
    def default_intrastat_cancelled():
        return False

    def get_shipment_price_list(self, name):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')

        if (self.shipment
                and isinstance(self.shipment, ShipmentInternal)):
            return self.shipment.price_list
        return None

    @classmethod
    def search_shipment_price_list(cls, name, clause):
        return [('shipment.price_list',) + tuple(clause[1:])
            + ('stock.shipment.internal',)]

    @property
    @fields.depends('shipment', 'shipment_price_list')
    def intrastat_to_country(self):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')

        # Control the internal consignment move. Need to appear in Intrastat
        if (self.shipment and isinstance(self.shipment, ShipmentInternal)
                and self.shipment_price_list
                and hasattr(self.shipment, 'intrastat_to_country')):
            return self.shipment.intrastat_to_country
        return super().intrastat_to_country

    @property
    @fields.depends('shipment', 'shipment_price_list')
    def intrastat_from_country(self):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')

        # Control the internal consignment move. Need to appear in Intrastat
        if (self.shipment and isinstance(self.shipment, ShipmentInternal)
                and self.shipment_price_list
                and hasattr(self.shipment, 'intrastat_from_country')):
            return self.shipment.intrastat_from_country
        return super().intrastat_from_country

    @fields.depends('shipment', 'shipment_price_list')
    def _get_intrastat_to_country(self):
        # ALERT source code from intrastat_to_country property
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')

        if (self.shipment and isinstance(self.shipment, ShipmentInternal)
                and self.shipment_price_list
                and hasattr(self.shipment, 'intrastat_to_country')):
            return self.shipment.intrastat_to_country
        return super()._get_intrastat_to_country()

    @fields.depends('company', '_parent_company.intrastat', 'shipment',
        'shipment_price_list', 'invoice_lines', 'origin')
    def on_change_with_intrastat_type(self):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')

        if (not self.company or not self.company.intrastat or (
                    self.shipment and isinstance(
                        self.shipment, ShipmentInternal)
                    and (not self.shipment_price_list
                        or (self.shipment_price_list
                            and self not in self.shipment.outgoing_moves)))):
            return
        # If the movement is "from" and "to" different Company country, then
        # it has not to be included in the Intrastat. Only the movements that
        # come "from" or "to" Company country must to be included.
        from_country = self.intrastat_from_country
        to_country = self.intrastat_to_country
        company_address = self.company.party.address_get(type='invoice')
        company_country = company_address.country if company_address else None
        if from_country and to_country and company_country:
            if (from_country != company_country
                    and to_country != company_country):
                return

        # If the sale/invoice relate to the move have National Tax, the move
        # has not to be in the Intrastat
        if self.move_tax_intrastat_exempt():
            return
        return super().on_change_with_intrastat_type()

    def _intrastat_value(self):
        pool = Pool()
        Move = pool.get('stock.move')
        Currency = pool.get('currency.currency')
        try:
            LandedCost = pool.get('account.landed_cost')
        except:
            LandedCost = None

        if self.shipment_price_list:
            ndigits = self.__class__.intrastat_value.digits[1]
            with Transaction().set_context(
                    date=self.effective_date or self.planned_date):
                unit_price = self.shipment_price_list.compute(
                    self.product, self.quantity, self.unit)
                if unit_price is not None:
                    unit_price = round(unit_price * Decimal(
                            str(self.quantity)), ndigits)
                return unit_price

        ndigits = Move.intrastat_value.digits[1]
        default_intrastat_value = round(self.product.cost_price, ndigits)
        intrastat_value_from_invoice = Decimal('0.0')
        invoices = [l.invoice for l in self.invoice_lines
            if l.invoice and l.invoice.state in ('posted', 'paid')]
        # TODO: Control correctly UoM
        quantity = sum(l.quantity for l in self.invoice_lines if l.quantity > 0)
        landed_costs = None
        # If Landed cost is set on a shipment, the intrastat value must be
        # calculated without this extra amount on unit_price.
        if LandedCost and self.shipment:
            landed_costs = LandedCost.search([
                    ('shipments','in',[self.shipment.id]),
            ])
            if landed_costs and self.unit_price is not None and self.currency:
                unit_price = self.unit_price - (
                    self.unit_landed_cost or Decimal('0.0'))
                ndigits = self.__class__.intrastat_value.digits[1]
                with Transaction().set_context(
                        date=self.effective_date or self.planned_date):
                    intrastat_value = round(Currency.compute(
                            self.currency,
                            unit_price * Decimal(str(self.quantity)),
                            self.company.intrastat_currency or self.currency,
                            round=False), ndigits)
            elif not self.currency:
                intrastat_value = Decimal('0.0')
        if not landed_costs:
            intrastat_value = (super()._intrastat_value()
                if self.currency else Decimal('0.0'))
        if invoices and quantity == self.quantity:
            intrastat_value_from_invoice = Move._intrastat_value_from_invoices(
                self, invoices, intrastat_value)
            with Transaction().set_context(
                    date=self.effective_date or self.planned_date):
                intrastat_value_from_invoice = round(Currency.compute(
                        self.currency,
                        intrastat_value_from_invoice,
                        self.company.intrastat_currency,
                        round=False), ndigits)

        return (intrastat_value_from_invoice or intrastat_value
            or default_intrastat_value)

    @classmethod
    def _update_intrastat(cls, moves):
        if not Transaction().context.get('_update_intrastat_declaration'):
            super()._update_intrastat(moves)

    def _set_intrastat(self):
        pool = Pool()
        try:
            SaleLine = pool.get('sale.line')
        except:
            SaleLine = None
        try:
            PurchaseLine = pool.get('purchase.line')
        except:
            PurchaseLine = None
        ShipmentIn = pool.get('stock.shipment.in')
        ShipmentInReturn = pool.get('stock.shipment.in.return')
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')
        Transport = pool.get('account.stock.eu.intrastat.transport')
        ShipmentInternal = pool.get('stock.shipment.internal')
        Incoterm = pool.get('incoterm.incoterm')

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

        if (not self.intrastat_transport and self.shipment
                and self.shipment.intrastat_transport):
            self.intrastat_transport = self.shipment.intrastat_transport

        if not self.intrastat_incoterm:
            # Try to set Incoterm from origin
            if self.origin:
                if SaleLine and isinstance(self.origin, SaleLine):
                    self.intrastat_incoterm = self.origin.sale.incoterm or None
                elif PurchaseLine and isinstance(self.origin, PurchaseLine):
                    self.intrastat_incoterm = (self.origin.purchase.incoterm
                        or None)
        if not self.intrastat_incoterm:
            # Try to set Incoterm from party
            shipment = self.shipment
            party_incoterms = []
            if isinstance(shipment, (ShipmentIn, ShipmentInReturn)):
                party_incoterms = shipment.supplier.purchase_incoterms
            if isinstance(shipment, (ShipmentOut, ShipmentOutReturn)):
                party_incoterms = shipment.customer.sale_incoterms
            if party_incoterms and len(party_incoterms) == 1:
                self.intrastat_incoterm = party_incoterms[0].incoterm

        # If the move came from an Internal move, the subdivision maybe is
        # not set.
        if (not self.intrastat_subdivision and self.intrastat_type
                and self.intrastat_type == 'dispatch' and self.shipment
                and isinstance(self.shipment, ShipmentInternal)
                and self.shipment_price_list
                and self.shipment.from_location
                and self.shipment.from_location.warehouse):
            from_warehouse = self.shipment.from_location.warehouse
            if (from_warehouse.address
                    and from_warehouse.address.subdivision):
                subdivision = from_warehouse.address.subdivision
                self.intrastat_subdivision = subdivision.get_intrastat()

        # If for some reason the intrastat_transport is not setted, we asume
        # it's Road transport, code 3.
        if not self.intrastat_transport and self.intrastat_type:
            transports = Transport.search([
                    ('code', '=', '3')
                ], limit=1)
            transport = transports[0] if transports else None
            self.intrastat_transport = transport

        # For Internal shipments with price_list, set a default Incoterm
        if (not self.intrastat_incoterm and self.intrastat_type
                and isinstance(self.shipment, ShipmentInternal)
                and self.shipment_price_list):
            incoterms = Incoterm.search([
                    ('code', '=', 'EXW')
                ], order=[('id', 'DESC')], limit=1)
            incoterm = incoterms[0] if incoterms else None
            self.intrastat_incoterm = incoterm

    def _intrastat_tariff_code_pattern_wo_country(self):
        return {
            'date': self.effective_date,
            }

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

    def _intrastat_quantity(self, unit):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        result = super()._intrastat_quantity(unit)
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

    def _intrastat_counterparty(self):
        pool = Pool()
        ShipmentInternal = pool.get('stock.shipment.internal')

        if (isinstance(self.shipment, ShipmentInternal)
                and self.shipment_price_list and self.shipment.to_location
                and self.shipment.to_location.warehouse
                and self.shipment.to_location.warehouse.address):
            return self.shipment.to_location.warehouse.address.party

        return super()._intrastat_counterparty()

    @classmethod
    def update_intrastat_declaration(cls, moves):
        pool = Pool()
        ShipmentIn = pool.get('stock.shipment.in')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')

        with Transaction().set_context(_update_intrastat_declaration=True):
            moves_to_reset = []
            for move in moves:
                if (move.invoice_lines
                        and any(line.invoice.state == 'cancelled'
                            for line in move.invoice_lines
                            if line.invoice is not None)):
                    moves_to_reset.append(move)
                elif move.move_tax_intrastat_exempt():
                    moves_to_reset.append(move)
                if move.shipment and isinstance(move.shipment, ShipmentIn):
                    move.shipment.on_change_supplier()
                elif (move.shipment
                        and isinstance(move.shipment, ShipmentOutReturn)):
                    move.shipment.on_change_customer()
                move.intrastat_type = move.on_change_with_intrastat_type()
                move._set_intrastat()
                if not move.internal_weight:
                    internal_weight = cls._get_internal_weight(
                        move.quantity, move.unit, move.product)
                    move.internal_weight = internal_weight or 0
            if moves_to_reset:
                cls.reset_intrastat(moves_to_reset)
            cls.save(moves)

    @classmethod
    def reset_intrastat(cls, moves):
        values = {
            'internal_volume': None,
            'internal_weight': None,
            'intrastat_additional_unit': None,
            'intrastat_country': None,
            'intrastat_country_of_origin': None,
            'intrastat_declaration': None,
            'intrastat_subdivision': None,
            'intrastat_tariff_code': None,
            'intrastat_transaction': None,
            'intrastat_type': None,
            'intrastat_value': None,
            'intrastat_vat': None,
            'intrastat_warehouse_country': None,
            'intrastat_incoterm': None,
            'intrastat_transport': None,
            'intrastat_cancelled': None,
            }
        cls.write(moves, values)

    def move_tax_intrastat_exempt(self):
        pool = Pool()
        Configuration = pool.get('stock.configuration')

        config = Configuration(1)
        if not config.intrastat_exempt_taxes:
            return False
        for line in self.invoice_lines:
            for tax in line.taxes:
                if tax in config.intrastat_exempt_taxes:
                    return True
        if hasattr(self, 'sale'):
            SaleLine = pool.get('sale.line')
            sale_line_taxes = (self.origin.taxes
                if isinstance(self.origin, SaleLine) else [])
            for tax in sale_line_taxes:
                if tax in config.intrastat_exempt_taxes:
                    return True
        return False

    @classmethod
    def do(cls, moves):
        pool = Pool()
        Company = pool.get('company.company')
        # As in "do" function when is called the _set_intrstat function is
        # checked if intrastat_type and intrastat_from_country and
        # intrastat_to_country are setted. If not, rasie a warning that in
        # the case that the company has intrastat not activated, it's not
        # necessary.
        company_id = Transaction().context.get('company')
        skip = (False if company_id is not None and company_id >= 0
            and Company(company_id).intrastat else True)
        with Transaction().set_context(_skip_warnings=skip):
            super().do(moves)

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
    total_intrastat_value = fields.Function(fields.Numeric(
            "Total Intrastat Value", digits=(16, 2), readonly=True),
        'get_total_intrastat_value')

    def get_total_intrastat_value(self, name):
        total = Decimal(0)
        for move in self.moves:
            if not move.intrastat_type or not move.intrastat_value:
                continue
            total += move.intrastat_value
        return total


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

    to_warehouse = fields.Function(
        fields.Many2One(
            'stock.location', "To Warehouse",
            help="Where the stock is sent to."),
        'on_change_with_to_warehouse')
    price_list = fields.Many2One(
        'product.price_list', "Price List",
        help="The price list used to calculate the Intrastata value it's "
            "required.",
        domain=[
            ('company', '=', Eval('company')),
            ],
        states={
            'invisible': (~Eval('intrastat_from_country')
                | ~Eval('intrastat_to_country')
                | (Eval('intrastat_from_country') ==
                    Eval('intrastat_to_country'))),
            'readonly': ~Eval('state').in_(['request', 'draft']),
            },)
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'on_change_with_currency')

    @fields.depends('to_location')
    def on_change_with_to_warehouse(self, name=None):
        return self.to_location.warehouse if self.to_location else None

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        currency_id = None
        if hasattr(self, 'valued_moves') and self.valued_moves:
            for move in self.valued_moves:
                if move.currency:
                    currency_id = move.currency.id
                    break
        if currency_id is None and self.company:
            currency_id = self.company.currency.id
        return currency_id


class ShipmentInReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class ShipmentOutReturn(ShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'


class MoveSale(metaclass=PoolMeta):
    __name__ = 'stock.move'

    @fields.depends('sale')
    def on_change_with_intrastat_type(self):
        return super().on_change_with_intrastat_type()
