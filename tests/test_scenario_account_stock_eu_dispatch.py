import datetime as dt
import io
import unittest
import zipfile
from decimal import Decimal

from proteus import Model, Wizard
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Imports
        today = dt.date.today()

        # Activate modules
        config = activate_modules('account_stock_eu_es')
        Country = Model.get('country.country')
        IntrastatDeclaration = Model.get(
            'account.stock.eu.intrastat.declaration')
        IntrastatDeclarationLine = Model.get(
            'account.stock.eu.intrastat.declaration.line')
        Organization = Model.get('country.organization')
        Party = Model.get('party.party')
        ProductTemplate = Model.get('product.template')
        ProductUom = Model.get('product.uom')
        ShipmentOut = Model.get('stock.shipment.out')
        ShipmentInReturn = Model.get('stock.shipment.in.return')
        ShipmentInternal = Model.get('stock.shipment.internal')
        StockLocation = Model.get('stock.location')
        TariffCode = Model.get('customs.tariff.code')
        PriceList = Model.get('product.price_list')

        # Create countries
        europe, = Organization.find([('code', '=', 'EU')])
        belgium = Country(name="Belgium", code='BE')
        belgium.subdivisions.new(name="Flemish Region",
                                               intrastat_code='1',
                                               type='region')
        belgium.subdivisions.new(name="Walloon Region",
                                               intrastat_code='2',
                                               type='region')
        belgium.save()
        flemish, walloon = belgium.subdivisions
        belgium.subdivisions.new(name="Liège",
                                               type='province',
                                               parent=walloon)
        belgium.save()
        liege, = [s for s in belgium.subdivisions if s.parent == walloon]
        france = Country(name="France", code='FR')
        france.save()
        united_state = Country(name="United State", code='US')
        united_state.save()
        china = Country(name="China", code='CN')
        china.save()
        europe.members.new(country=belgium)
        europe.members.new(country=france)
        europe.save()

        # Create currency
        eur = get_currency('EUR')
        usd = get_currency('USD')

        # Create company in Belgium
        _ = create_company(currency=eur)
        company = get_company()
        self.assertEqual(company.intrastat, True)
        company_address, = company.party.addresses
        company_address.country = belgium
        company_address.subdivision = liege
        company_address.save()

        # Create suppliers
        customer_be = Party(name="Customer BE")
        address, = customer_be.addresses
        address.country = belgium
        customer_be.save()
        supplier_fr = Party(name="Supplier FR")
        address, = supplier_fr.addresses
        address.country = france
        identifier = supplier_fr.identifiers.new(type='eu_vat')
        identifier.code = "FR40303265045"
        supplier_fr.save()
        customer_fr = Party(name="Customer FR")
        identifier = customer_fr.identifiers.new(type='eu_vat')
        identifier.code = "FR40303265045"
        address_fr, = customer_fr.addresses
        address_fr.country = france
        customer_fr.save()
        address_fr.save()
        customer_us = Party(name="Customer US")
        address, = customer_us.addresses
        address.country = united_state
        customer_us.save()

        # Create product
        unit, = ProductUom.find([('name', '=', "Unit")])
        kg, = ProductUom.find([('name', '=', "Kilogram")])
        tariff_code = TariffCode(code="9403 10 51")
        tariff_code.description = "Desks"
        tariff_code.intrastat_uom = unit
        tariff_code.save()
        template = ProductTemplate(name="Desk")
        template.default_uom = unit
        template.type = 'goods'
        template.cost_price = Decimal('100.0000')
        _ = template.tariff_codes.new(tariff_code=tariff_code)
        template.weight = 3
        template.weight_uom = kg
        template.country_of_origin = china
        template.save()
        product, = template.products

        # Get stock locations
        warehouse_loc, = StockLocation.find([('code', '=', 'WH')])
        warehouse_loc.address = company_address
        warehouse_loc.save()

        # Send products to Belgium
        shipment = ShipmentOut()
        shipment.customer = customer_be
        move = shipment.outgoing_moves.new()
        move.from_location = shipment.warehouse_output
        move.to_location = shipment.customer_location
        move.product = product
        move.quantity = 10
        move.unit_price = Decimal('100.0000')
        move.currency = eur
        shipment.click('wait')
        shipment.click('pick')
        shipment.click('pack')
        shipment.click('done')
        self.assertEqual(shipment.state, 'done')
        move, = shipment.inventory_moves
        move.intrastat_type
        move, = shipment.outgoing_moves
        move.intrastat_type

        # Send products to particular to France
        shipment = ShipmentOut()
        shipment.customer = customer_fr
        move = shipment.outgoing_moves.new()
        move.from_location = shipment.warehouse_output
        move.to_location = shipment.customer_location
        move.product = product
        move.quantity = 20
        move.unit_price = Decimal('90.0000')
        move.currency = eur
        shipment.click('wait')
        shipment.click('pick')
        shipment.click('pack')
        shipment.click('done')
        self.assertEqual(shipment.state, 'done')
        move, = shipment.inventory_moves
        move.intrastat_type
        move, = shipment.outgoing_moves
        self.assertEqual(move.intrastat_type, 'dispatch')
        self.assertEqual(move.intrastat_warehouse_country.code, 'BE')
        self.assertEqual(move.intrastat_country.code, 'FR')
        self.assertEqual(move.intrastat_subdivision.intrastat_code, '2')
        self.assertEqual(move.intrastat_tariff_code.code, '9403 10 51')
        self.assertEqual(move.intrastat_value, Decimal('1800.00'))
        self.assertEqual(move.intrastat_transaction.code, '11')
        self.assertEqual(move.intrastat_additional_unit, 20.0)
        self.assertEqual(move.intrastat_country_of_origin.code, 'CN')
        move.intrastat_vat
        self.assertEqual(move.intrastat_declaration.month, today.replace(day=1))

        # Send products to US
        shipment = ShipmentOut()
        shipment.customer = customer_us
        move = shipment.outgoing_moves.new()
        move.from_location = shipment.warehouse_output
        move.to_location = shipment.customer_location
        move.product = product
        move.quantity = 30
        move.unit_price = Decimal('120.0000')
        move.currency = usd
        shipment.click('wait')
        shipment.click('pick')
        shipment.click('pack')
        shipment.click('done')
        self.assertEqual(shipment.state, 'done')
        move, = shipment.inventory_moves
        move.intrastat_type
        move, = shipment.outgoing_moves
        move.intrastat_type

        # Send returned products to France
        shipment = ShipmentInReturn()
        shipment.supplier = supplier_fr
        shipment.from_location = warehouse_loc.storage_location
        move = shipment.moves.new()
        move.from_location = shipment.from_location
        move.to_location = shipment.to_location
        move.product = product
        move.quantity = 5
        move.unit_price = Decimal('150.0000')
        move.currency = eur
        shipment.click('wait')
        shipment.click('assign_force')
        shipment.click('done')
        self.assertEqual(shipment.state, 'done')
        move, = shipment.moves
        self.assertEqual(move.intrastat_type, 'dispatch')
        self.assertEqual(move.intrastat_warehouse_country.code, 'BE')
        self.assertEqual(move.intrastat_country.code, 'FR')
        self.assertEqual(move.intrastat_subdivision.intrastat_code, '2')
        self.assertEqual(move.intrastat_tariff_code.code, '9403 10 51')
        self.assertEqual(move.intrastat_value, Decimal('750.00'))
        self.assertEqual(move.intrastat_transaction.code, '21')
        self.assertEqual(move.intrastat_additional_unit, 5.0)
        self.assertEqual(move.intrastat_country_of_origin.code, 'CN')
        self.assertEqual(move.intrastat_vat.code, 'FR40303265045')
        self.assertEqual(move.intrastat_declaration.month, today.replace(day=1))

        # Create consignment stock locations
        warehouse_consignment_id, = StockLocation.copy([warehouse_loc],
            config.context)
        warehouse_consignment = StockLocation(warehouse_consignment_id)
        warehouse_consignment.name = 'Consignment'
        warehouse_consignment.address = address_fr
        warehouse_consignment.save()

        # Create a price List
        price_list = PriceList(name='Retail')
        price_list_line = price_list.lines.new()
        price_list_line.quantity = 1
        price_list_line.product = product
        price_list_line.formula = '100.00'
        price_list_line = price_list.lines.new()
        price_list_line.formula = 'cost_price'
        price_list.save()

        # Move product from consignment location setting the price list
        shipment = ShipmentInternal()
        shipment.from_location = warehouse_loc.storage_location
        shipment.to_location = warehouse_consignment.storage_location
        shipment.price_list = price_list
        move = shipment.moves.new()
        move.from_location = shipment.from_location
        move.to_location = shipment.to_location
        move.product = product
        move.quantity = 10
        move.currency = eur
        shipment.click('wait')
        shipment.click('assign_force')
        shipment.click('ship')
        shipment.click('done')
        self.assertEqual(shipment.state, 'done')
        move, = shipment.incoming_moves
        move.intrastat_type
        move, = shipment.outgoing_moves
        self.assertEqual(move.intrastat_type, 'dispatch')
        self.assertEqual(move.intrastat_warehouse_country.code, 'BE')
        self.assertEqual(move.intrastat_country.code, 'FR')
        self.assertEqual(move.intrastat_subdivision.intrastat_code, '2')
        self.assertEqual(move.intrastat_tariff_code.code, '9403 10 51')
        self.assertEqual(move.intrastat_value, Decimal('1000.00'))
        self.assertEqual(move.intrastat_transaction.code, '31')
        self.assertEqual(move.intrastat_additional_unit, 10.0)
        self.assertEqual(move.intrastat_country_of_origin.code, 'CN')
        self.assertEqual(move.intrastat_vat.code, 'FR40303265045')
        self.assertEqual(move.intrastat_declaration.month, today.replace(day=1))

        # Check declaration
        declaration, = IntrastatDeclaration.find([])
        self.assertEqual(declaration.country.code, 'BE')
        self.assertEqual(declaration.month, today.replace(day=1))
        self.assertEqual(declaration.state, 'opened')
        with config.set_context(declaration=declaration.id):

            declaration_line = IntrastatDeclarationLine.find([])[0]
        self.assertEqual(declaration_line.type, 'dispatch')
        self.assertEqual(declaration_line.country.code, 'FR')
        self.assertEqual(declaration_line.subdivision.intrastat_code, '2')
        self.assertEqual(declaration_line.tariff_code.code, '9403 10 51')
        self.assertEqual(declaration_line.weight, 60.0)
        self.assertEqual(declaration_line.value, Decimal('1800.00'))
        self.assertEqual(declaration_line.transaction.code, '11')
        self.assertEqual(declaration_line.additional_unit, 20.0)
        self.assertEqual(declaration_line.country_of_origin.code, 'CN')
        self.assertEqual(move.intrastat_vat.code, 'FR40303265045')

        # Export declaration
        _ = declaration.click('export')
        export = Wizard('account.stock.eu.intrastat.declaration.export',
                        [declaration])
        self.assertEqual(export.form.filename.endswith('.csv'), True)
        self.assertEqual(
            export.form.file,
            b'29;FR;11;2;9403 10 51;60.0;20.0;1800.00;;;CN;FR40303265045\r\n29;FR;21;2;9403 10 51;15.0;5.0;750.00;;;CN;FR40303265045\r\n29;FR;31;2;9403 10 51;30.0;10.0;1000.00;;;CN;FR40303265045\r\n'
        )
        self.assertEqual(declaration.state, 'closed')

        # Export declaration as Spain
        belgium.code = 'ES'
        belgium.save()
        _ = declaration.click('export')
        export = Wizard('account.stock.eu.intrastat.declaration.export',
                        [declaration])
        self.assertEqual(export.form.filename.endswith('.zip'), True)
        zip = zipfile.ZipFile(io.BytesIO(export.form.file))
        self.assertEqual(zip.namelist(), ['dispatch-0.csv'])
        a = zip.open('dispatch-0.csv').read()
        self.assertEqual(
            zip.open('dispatch-0.csv').read(),
            #b'FR;2;;12;;;9403 10 51;CN;;60.000;20.0;1800.00;1800.00;\r\nFR;2;;21;;;9403 10 51;CN;;15.000;5.0;750.00;750.00;FR40303265045\r\n'
            b'FR;2;;11;;;9403 10 51;CN;;60.000;20.0;1800.00;1800.00;FR40303265045\r\nFR;2;;21;;;9403 10 51;CN;;15.000;5.0;750.00;750.00;FR40303265045\r\nFR;2;;31;;;9403 10 51;CN;;30.000;10.0;1000.00;1000.00;FR40303265045\r\n'
        )

        # Export declaration as fallback
        belgium.code = 'XX'
        belgium.save()
        _ = declaration.click('export')
        export = Wizard('account.stock.eu.intrastat.declaration.export',
                        [declaration])
        self.assertEqual(export.form.filename.endswith('.csv'), True)
        self.assertEqual(
            export.form.file,
            b'dispatch,FR,2,9403 10 51,60.0,1800.00,11,20.0,CN,FR40303265045,3,\r\ndispatch,FR,2,9403 10 51,15.0,750.00,21,5.0,CN,FR40303265045,3,\r\ndispatch,FR,2,9403 10 51,30.0,1000.00,31,10.0,CN,FR40303265045,3,EXW\r\n'
        )
