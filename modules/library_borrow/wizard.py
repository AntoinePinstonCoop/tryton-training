import datetime

from sql import Null

from trytond.pool import Pool
from trytond.pyson import PYSONEncoder, Eval
from trytond.transaction import Transaction
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, StateAction
from trytond.wizard import Button

__all__ = [
    'BorrowBook',
    'ChooseBook',
    'ReturnBook',
    'ChooseReturningBook',
    ]


class BorrowBook(Wizard):
    "Borrow books"

    __name__ = "library.checkout.borrow_book"

    start_state = "choose_book"
    choose_book = StateView('library.checkout.borrow_book.choose_book',
        'library_borrow.checkout_book_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Borrow book', 'create_checkout', 'tryton-go-next'), ])
    create_checkout = StateTransition()
    open_checkout = StateAction('library_borrow.act_open_user_checkout')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
            'invalid_model': (
                'This action should be started from a book or an user'
                ),
            'invalid_date': 'You cannot checkout books in the future',
            'not_available': (
                'One of the selected books are not available for booking'
                ),
        })

    def default_choose_book(self, name):
        if Transaction().context.get('active_model', '') == 'library.book':
            books = Transaction().context.get('active_ids')
            for book in books:
                if self._find_free_exemplary(book) is None:
                    self.raise_user_error('not_available')
            return {
                'borrow_date': datetime.date.today(),
                'books': books,
                }
        elif Transaction().context.get('active_model', '') == 'library.user':
            return {
                'borrow_date': datetime.date.today(),
                'user': Transaction().context.get('active_id'),
                }
        else:
            self.raise_user_error('invalid_model')

    def transition_create_checkout(self):
        if (self.choose_book.borrow_date > datetime.date.today()):
            self.raise_user_error('invalid_date')
        Checkout = Pool().get('library.user.checkout')
        to_create = []
        for book in self.choose_book.books:
            checkout = Checkout()
            checkout.user = self.choose_book.user
            checkout.date = self.choose_book.borrow_date
            checkout.exemplary = self._find_free_exemplary(book.id)
            to_create.append(checkout)
        Checkout.save(to_create)
        self.choose_book.checkout = to_create
        return 'open_checkout'

    def do_open_checkout(self, action):
        action['pyson_domain'] = PYSONEncoder().encode([
                ('id', 'in', [x.id for x in self.choose_book.checkout])])
        return action, {}

    def _find_free_exemplary(self, book_id) -> int:
        # Find the first free exemplary of a book
        pool = Pool()
        checkout = pool.get('library.user.checkout').__table__()
        exemplary = pool.get('library.book.exemplary').__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(*exemplary.join(checkout, 'LEFT OUTER',
                    condition=(exemplary.id == checkout.exemplary)
                ).select(exemplary.id,
                    where=(((checkout.return_date != Null)
                            | (checkout.id == Null))
                        & (exemplary.book == book_id)),
                    group_by=[exemplary.id]))
        result_query = cursor.fetchone()
        if result_query:
            return result_query[0]


class ChooseBook(ModelView):
    "Choose books"

    __name__ = "library.checkout.borrow_book.choose_book"

    user = fields.Many2One('library.user', "User", required=True)
    books = fields.Many2Many('library.book', None, None, "Books to borrow")
    checkout = fields.Many2Many('library.user.checkout', None, None,
        'Checkout')

    borrow_date = fields.Date("Borrowing date", "", required=True,
        domain=[("borrow_date", "<=", datetime.date.today())])
    expected_return_date = fields.Function(
        fields.Date("Expected return date", readonly=True),
        getter="on_change_with_expected_return_date",
        )

    @fields.depends("borrow_date")
    def on_change_with_expected_return_date(self):
        return self.borrow_date + datetime.timedelta(20)


class ReturnBook(Wizard):
    "Return books"

    __name__ = "library.checkout.return_book"

    start_state = "choose_return_book"
    choose_return_book = StateView(
        'library.checkout.return_book.choose_return_book',
        'library_borrow.return_book_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Return book', 'return_book', 'tryton-go-next'), ])
    return_book = StateTransition()

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._error_messages.update({
            'invalid_model': (
                'This action should be started from a book or an user'
                ), })

    def default_choose_return_book(self, name):
        active_model = Transaction().context.get('active_model', '')
        if active_model == 'library.user.checkout':
            checkouts = Transaction().context.get('active_ids')
            return {
                'return_date': datetime.date.today(),
                'checkouts': checkouts,
                }
        elif active_model == 'library.user':
            user_checkout = []
            user = Transaction().context.get('active_id')
            checkout = Pool().get('library.user.checkout').__table__()

            cursor = Transaction().connection.cursor()
            cursor.execute(*checkout.select(checkout.id,
                where=((checkout.user.in_([user]))
                       & (checkout.return_date == Null)),
                group_by=[checkout.id]))
            for checkout_id, in cursor.fetchall():
                user_checkout.append(checkout_id)
            return {
                'user': user,
                'checkouts': user_checkout,
                'return_date': datetime.date.today(),
                }
        else:
            self.raise_user_error('invalid_model')

    def transition_return_book(self):
        for checkout in self.choose_return_book.checkouts:
            if checkout.return_date is None:
                setattr(checkout, "return_date",
                    self.choose_return_book.return_date)
            checkout.save()
        return 'end'


class ChooseReturningBook(ModelView):
    "Choose returning books"

    __name__ = "library.checkout.return_book.choose_return_book"

    user = fields.Many2One('library.user', 'User', required=True)
    checkouts = fields.Many2Many('library.user.checkout', None, None,
        "Books to return", domain=[('user', '=', Eval('user'))])
    return_date = fields.Date("Return date", "", required=True,
        domain=[('return_date', '<=', datetime.date.today())])
