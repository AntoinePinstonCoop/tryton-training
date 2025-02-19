from trytond.pool import Pool

from . import library
from . import wizard


def register():
    Pool.register(
        library.Room,
        library.Shelf,
        library.Quarantine,
        library.Book,
        library.Exemplary,
        wizard.SelectSafeQuarantine,
        wizard.CreateExemplariesParameters,
        module='library_localisation', type_='model')

    Pool.register(
        wizard.SafeFromQuarantine,
        wizard.Return,
        wizard.CreateExemplaries,
        module='library_localisation', type_='wizard')
