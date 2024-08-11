from __future__ import annotations

import attrs
from zope.interface import Interface, implementer

from twisted.trial.unittest import SynchronousTestCase

from .._attrs_zope import provides


class IWhatever(Interface):
    ...


@implementer(IWhatever)
class YesWhatever:
    ...


class NoWhatever:
    ...


@attrs.define()
class WhateverContainer:
    whatever: object = attrs.field(validator=provides(IWhatever))


class ProvidesTestCase(SynchronousTestCase):
    def test_yes(self) -> None:
        WhateverContainer(YesWhatever())

    def test_no(self) -> None:
        with self.assertRaises(TypeError):
            WhateverContainer(NoWhatever())
