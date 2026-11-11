"""Generators for common instruction sequences."""


def nop(repeat):
    """The given number of nops."""
    return "nop\n" * repeat


def ldax(value):
    """Load a 16-bit value: the low byte in A, and the high byte in X."""
    a = lo(value)
    x = hi(value)
    if a == x:
        return f"""
        lda #{a}
        tax
        """
    else:
        return f"""
        lda #{a}
        ldx #{x}
        """


def lday(value):
    """Load a 16-bit value: the low byte in A, and the high byte in Y."""
    a = lo(value)
    y = hi(value)
    if a == y:
        return f"""
        lda #{a}
        tay
        """
    else:
        return f"""
        lda #{a}
        ldy #{y}
        """


def ldxy(value):
    """Load a 16-bit value: the low byte in X, and the high byte in Y."""
    x = lo(value)
    y = hi(value)
    return f"""
    ldx #{x}
    ldy #{y}
    """


def stax(address):
    """Store A and X as a 16-bit value at the address, low byte first."""
    return f"""
    sta {address}
    stx {address+1}
    """


def stay(address):
    """Store A and Y as a 16-bit value at the address, low byte first."""
    return f"""
    sta {address}
    sty {address+1}
    """


def stxy(address):
    """Store X and Y as a 16-bit value at the address, low byte first."""
    return f"""
    stx {address}
    sty {address+1}
    """
