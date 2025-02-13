from trytond.pool import Pool

from . import library
from . import wizard


def register():
    Pool.register(
        library.User,
        library.Checkout,
        library.Exemplary,
        library.Book,
        wizard.ChooseBook,
        wizard.ChooseReturningBook,
        module="library_borrow", type_="model"
    )

    Pool.register(
        wizard.BorrowBook,
        wizard.ReturnBook,
        module="library_borrow", type_="wizard"
    )
