import datetime

from sql import Null
from sql.operators import NotIn
from sql.aggregate import Count
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval, Bool


__all__ = [
    'Room',
    'Shelf',
    'Quarantine',
    'Book',
    'Exemplary',
    ]


class Room(ModelSQL, ModelView):
    'Room'
    __name__ = 'library.localisation.room'

    shelfs = fields.One2Many('library.localisation.room.shelf',
        "room", "Shelfs")

    name = fields.Char('Room name', required=True)
    floor = fields.Integer('Floor number', 'Floor number of the room',
        required=True)


class Shelf(ModelSQL, ModelView):
    'Shelf'
    __name__ = 'library.localisation.room.shelf'

    room = fields.Many2One('library.localisation.room', "room", "Room",
        required=True, ondelete="CASCADE")
    exemplaries = fields.One2Many('library.book.exemplary', "shelf",
        "Exemplaries", readonly=True)
    name = fields.Char('Name of the shelf', required=True)
    is_store = fields.Boolean("Is the store",
        "Check if the shelf is the store",
        states={'invisible': Bool(Eval('has_store'))},
        depends=['has_store'])

    has_store = fields.Function(fields.Boolean("Has a store been defined",
            "Function used to make the state visible/invisible of is_store"),
        getter="getter_has_store")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
                'duplicate_store': 'Their can only be one store',
                })

    @classmethod
    def validate(cls, shelfs):
        # Make the store a special shelf that can only be unique
        shelf = cls.__table__()

        cursor = Transaction().connection.cursor()

        cursor.execute(*shelf.select(Count(shelf.id),
                where=(shelf.is_store)))
        number_of_store = cursor.fetchone()[0]

        if number_of_store > 1:
            cls.raise_user_error('duplicate_store')

    def getter_has_store(self, name):
        Shelf = Pool().get('library.localisation.room.shelf')
        shelf = Shelf.__table__()

        cursor = Transaction().connection.cursor()

        cursor.execute(*shelf.select(Count(shelf.id),
                where=(shelf.is_store)))
        number_of_store = cursor.fetchone()[0]

        return bool(number_of_store)


class Quarantine(ModelSQL, ModelView):
    'Quarantine'
    __name__ = 'library.localisation.quarantine'

    exemplary = fields.Many2One('library.book.exemplary', "Exemplary",
        required=True, ondelete='CASCADE')

    date = fields.Date('Quarantine date', 'When was the book quarantined',
        required=True, domain=[("date", "<=", datetime.date.today())])

    expected_out_quarantine = fields.Function(fields.Date(
            "Expected return date",
            "7 days after the book was put in quarantine", readonly=True),
        getter="on_change_with_expected_out_quarantine")

    @classmethod
    def default_date(cls):
        return datetime.date.today()

    @fields.depends('date')
    def on_change_with_expected_out_quarantine(self, name=None):
        return self.date + datetime.timedelta(days=7)


class Book(metaclass=PoolMeta):
    __name__ = 'library.book'

    is_available = fields.Function(fields.Boolean("Is availabe",
            "Is an exemplary of the book available", readonly=True),
        'getter_is_available')

    @classmethod
    def getter_is_available(cls, books, name):
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = pool.get('library.book.exemplary').__table__()
        quarantine = Pool().get('library.localisation.quarantine').__table__()
        shelf = Pool().get('library.localisation.room.shelf').__table__()
        book = cls.__table__()

        result = {x.id: False for x in books}
        cursor = Transaction().connection.cursor()

        # All exemplaries in quarantine
        quarantine_store_exemplary = set()
        cursor.execute(*quarantine.select(quarantine.exemplary))
        for exemplary_id, in cursor.fetchall():
            quarantine_store_exemplary.add(exemplary_id)

        # ALl exemplaries in the reserve
        cursor.execute(*exemplary.join(
                shelf, condition=(shelf.id == exemplary.shelf)
        ).select(exemplary.id, where=shelf.is_store))
        for exemplary_id, in cursor.fetchall():
            quarantine_store_exemplary.add(exemplary_id)

        # Add the condition if an exemplary isn't quarantined or in the reserve
        cursor.execute(*book.join(exemplary,
                condition=(exemplary.book == book.id)
                ).join(checkout, 'LEFT OUTER',
                condition=(exemplary.id == checkout.exemplary)
                ).select(book.id,
                where=((checkout.return_date != Null) | (checkout.id == Null))
                & NotIn(exemplary.id, list(quarantine_store_exemplary))))
        for book_id, in cursor.fetchall():
            result[book_id] = True
        return result


class Exemplary(metaclass=PoolMeta):
    __name__ = 'library.book.exemplary'

    shelf = fields.Many2One('library.localisation.room.shelf', "shelf",
        required=True, ondelete='RESTRICT')
    is_available = fields.Function(fields.Boolean("Is availabe",
        "Is this exemplary available", readonly=True), "getter_is_available")

    @classmethod
    def getter_is_available(cls, exemplaries, name):
        quarantine = Pool().get('library.localisation.quarantine').__table__()
        shelf = Pool().get('library.localisation.room.shelf').__table__()
        exemplary = cls.__table__()
        cursor = Transaction().connection.cursor()

        result = {x.id: True for x in exemplaries}

        cursor.execute(*quarantine.select(quarantine.exemplary,
                where=quarantine.exemplary.in_([x.id for x in exemplaries])))
        for exemplary_id, in cursor.fetchall():
            result[exemplary_id] = False

        cursor.execute(*exemplary.join(
                shelf, condition=(shelf.id == exemplary.shelf)
        ).select(exemplary.id, where=shelf.is_store))
        for exemplary_id, in cursor.fetchall():
            result[exemplary_id] = False

        return result
