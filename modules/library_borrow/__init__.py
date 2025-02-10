from trytond.pool import Pool

from . import library


def register():
    Pool.register(
        library.User,
        library.Checkout, 
        library.Exemplary,
        module="library_borrow", type_="model"
    )