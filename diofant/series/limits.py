from diofant.core import S, Symbol, sympify, Expr, Rational, Float, PoleError
from diofant.core.symbol import Dummy
from diofant.functions.elementary.trigonometric import sin, cos
from .order import Order
from .gruntz import limitinf


def limit(expr, z, z0, dir="+"):
    """
    Compute the directional limit of ``expr`` at the point ``z0``.

    Examples
    ========

    >>> from diofant import limit, sin, oo
    >>> from diofant.abc import x
    >>> limit(sin(x)/x, x, 0)
    1
    >>> limit(1/x, x, 0, dir="+")
    oo
    >>> limit(1/x, x, 0, dir="-")
    -oo
    >>> limit(1/x, x, oo)
    0

    See Also
    ========

    Limit
    """

    return Limit(expr, z, z0, dir).doit(deep=False)


def heuristics(e, z, z0, dir):
    rv = None

    if abs(z0) is S.Infinity:
        rv = limit(e.subs(z, 1/z), z, S.Zero, "+" if z0 is S.Infinity else "-")
        if isinstance(rv, Limit):
            return
    elif e.is_Mul or e.is_Add or e.is_Pow or e.is_Function:
        r = []
        for a in e.args:
            l = limit(a, z, z0, dir)
            if l.has(S.Infinity) and (l.func not in (sin, cos) and
                                      l.is_finite is None):
                return
            elif isinstance(l, Limit):
                return
            elif l is S.NaN:
                return
            else:
                r.append(l)
        if r:
            rv = e.func(*r)
            if rv is S.NaN:
                return

    return rv


class Limit(Expr):
    r"""Represents a directional limit of ``expr`` at the point ``z0``.

    Parameters
    ==========

    expr : Expr
        algebraic expression
    z    : Symbol
        variable of the ``expr``
    z0   : Expr
        limit point, `z_0`
    dir  : {"+", "-", "real"}, optional
        For ``dir="+"`` (default) it calculates the limit from the right
        (`z\to z_0 + 0`) and for ``dir="-"`` the limit from the left (`z\to
        z_0 - 0`).  If ``dir="real"``, the limit is the bidirectional real
        limit.  For infinite ``z0`` (``oo`` or ``-oo``), the ``dir`` argument
        is determined from the direction of the infinity (i.e.,
        ``dir="-"`` for ``oo``).

    Examples
    ========

    >>> from diofant import Limit, sin
    >>> from diofant.abc import x
    >>> Limit(sin(x)/x, x, 0)
    Limit(sin(x)/x, x, 0)
    >>> Limit(1/x, x, 0, dir="-")
    Limit(1/x, x, 0, dir='-')
    """

    def __new__(cls, e, z, z0, dir="+"):
        e = sympify(e)
        z = sympify(z)
        z0 = sympify(z0)

        if z0 is S.Infinity:
            dir = "-"
        elif z0 is S.NegativeInfinity:
            dir = "+"

        if isinstance(dir, str):
            dir = Symbol(dir)
        elif not isinstance(dir, Symbol):
            raise TypeError("direction must be of type str or Symbol, not %s" % type(dir))
        if str(dir) not in ('+', '-', 'real'):
            raise ValueError(
                "direction must be either '+' or '-' or 'real', not %s" % dir)

        obj = Expr.__new__(cls)
        obj._args = (e, z, z0, dir)
        return obj

    @property
    def free_symbols(self):
        e, z, z0 = self.args[:3]
        return (e.free_symbols - z.free_symbols) | z0.free_symbols

    def doit(self, **hints):
        """Evaluates limit.

        Notes
        =====

        First we handle some trivial cases (i.e. constant), then try
        Gruntz algorithm (see the :py:mod:`~diofant.series.gruntz` module).
        """
        e, z, z0, dir = self.args

        if hints.get('deep', True):
            e = e.doit(**hints)
            z = z.doit(**hints)
            z0 = z0.doit(**hints)

        if str(dir) == 'real':
            right = limit(e, z, z0, "+")
            left = limit(e, z, z0, "-")
            if not (left - right).equals(0):
                raise PoleError("left and right limits for expression %s at "
                                "point %s=%s seems to be not equal" % (e, z, z0))
            else:
                return right

        use_heuristics = hints.get('heuristics', True)

        has_Floats = e.has(Float)
        if has_Floats:
            e = e.subs({k: Rational(k) for k in e.atoms(Float)},
                       simultaneous=True)

        if z0.has(z):
            newz = z.as_dummy()
            r = limit(e.subs(z, newz), newz, z0, dir)
            if r.func is Limit:
                r = r.subs(newz, z)
            return r

        if e == z:
            return z0

        if not e.has(z):
            return e

        if z0 is S.NaN:
            return S.NaN

        if e.has(Order):
            e = e.expand()
            order = e.getO()
            if order:
                if (z, z0) in zip(order.variables, order.point):
                    order = limit(order.expr, z, z0, dir)
                    e = e.removeO() + order

        try:
            # Convert to the limit z->oo and use Gruntz algorithm.
            newe, newz = e, z
            if z0 == S.NegativeInfinity:
                newe = e.subs(z, -z)
            elif z0 != S.Infinity:
                if str(dir) == "+":
                    newe = e.subs(z, z0 + 1/z)
                else:
                    newe = e.subs(z, z0 - 1/z)

            if not z.is_positive or not z.is_finite:
                # We need a fresh variable here to simplify expression further.
                newz = Dummy(z.name, positive=True, finite=True)
                newe = newe.subs(z, newz)

            r = limitinf(newe, newz)
        except (PoleError, ValueError, NotImplementedError):
            r = None
            if use_heuristics:
                r = heuristics(e, z, z0, dir)
            if r is None:
                return self

        if has_Floats:
            r = r.evalf()

        return r