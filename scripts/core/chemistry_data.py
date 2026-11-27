"""Periodic table reference, molar mass verification, and science rubric notation formatting."""

from fractions import Fraction
import re

# Standard IUPAC atomic weights (or mass number of longest-lived isotope for radioactive elements),
# indexed in order of atomic number 1..118.
_PERIODIC_TABLE = (
    ("H", 1.008), ("He", 4.0026),
    ("Li", 6.94), ("Be", 9.0122), ("B", 10.81), ("C", 12.011), ("N", 14.007),
    ("O", 15.999), ("F", 18.998), ("Ne", 20.180),
    ("Na", 22.990), ("Mg", 24.305), ("Al", 26.982), ("Si", 28.085), ("P", 30.974),
    ("S", 32.06), ("Cl", 35.45), ("Ar", 39.948),
    ("K", 39.098), ("Ca", 40.078), ("Sc", 44.956), ("Ti", 47.867), ("V", 50.942),
    ("Cr", 51.996), ("Mn", 54.938), ("Fe", 55.845), ("Co", 58.933), ("Ni", 58.693),
    ("Cu", 63.546), ("Zn", 65.38), ("Ga", 69.723), ("Ge", 72.630), ("As", 74.922),
    ("Se", 78.971), ("Br", 79.904), ("Kr", 83.798),
    ("Rb", 85.468), ("Sr", 87.62), ("Y", 88.906), ("Zr", 91.224), ("Nb", 92.906),
    ("Mo", 95.95), ("Tc", 98.0), ("Ru", 101.07), ("Rh", 102.91), ("Pd", 106.42),
    ("Ag", 107.868), ("Cd", 112.414), ("In", 114.818), ("Sn", 118.710), ("Sb", 121.760),
    ("Te", 127.60), ("I", 126.904), ("Xe", 131.293),
    ("Cs", 132.905), ("Ba", 137.327), ("La", 138.905), ("Ce", 140.116), ("Pr", 140.908),
    ("Nd", 144.242), ("Pm", 145.0), ("Sm", 150.36), ("Eu", 151.964), ("Gd", 157.25),
    ("Tb", 158.925), ("Dy", 162.500), ("Ho", 164.930), ("Er", 167.259), ("Tm", 168.934),
    ("Yb", 173.045), ("Lu", 174.967), ("Hf", 178.49), ("Ta", 180.948), ("W", 183.84),
    ("Re", 186.207), ("Os", 190.23), ("Ir", 192.217), ("Pt", 195.084), ("Au", 196.967),
    ("Hg", 200.592), ("Tl", 204.38), ("Pb", 207.2), ("Bi", 208.980), ("Po", 209.0),
    ("At", 210.0), ("Rn", 222.0),
    ("Fr", 223.0), ("Ra", 226.0), ("Ac", 227.0), ("Th", 232.038), ("Pa", 231.036),
    ("U", 238.029), ("Np", 237.0), ("Pu", 244.0), ("Am", 243.0), ("Cm", 247.0),
    ("Bk", 247.0), ("Cf", 251.0), ("Es", 252.0), ("Fm", 257.0), ("Md", 258.0),
    ("No", 259.0), ("Lr", 266.0), ("Rf", 267.0), ("Db", 268.0), ("Sg", 269.0),
    ("Bh", 270.0), ("Hs", 277.0), ("Mt", 278.0), ("Ds", 281.0), ("Rg", 282.0),
    ("Cn", 285.0), ("Nh", 286.0), ("Fl", 289.0), ("Mc", 290.0), ("Lv", 293.0),
    ("Ts", 294.0), ("Og", 294.0),
)

ATOMIC_NUMBERS = {symbol: z for z, (symbol, _) in enumerate(_PERIODIC_TABLE, 1)}
ATOMIC_WEIGHTS = {symbol: weight for symbol, weight in _PERIODIC_TABLE}
ELEMENT_SYMBOLS = frozenset(ATOMIC_NUMBERS)

_SUB_TRANS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUP_TRANS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
_HOMONUCLEAR_SINGLE = frozenset({"H2", "O2", "O3", "N2", "F2", "P4", "S8", "I2", "C60"})


def sort_atomic_masses(masses):
    """Return a dict of relative atomic masses ordered by ascending atomic number."""
    return dict(sorted(masses.items(), key=lambda item: (ATOMIC_NUMBERS.get(item[0], 999), item[0])))


def _strip_tex_wrappers(text):
    value = text.replace(r"\(", "").replace(r"\)", "").replace("$", "")
    value = re.sub(r"\\(?:left|right)\b", "", value)
    value = re.sub(r"\\[,;! ]", "", value)
    value = re.sub(r"\\(?:cdot|bullet)\b", "·", value)
    for _ in range(4):
        updated = re.sub(r"\\(?:mathrm|text|rm)\s*\{([^{}]*)\}", r"\1", value)
        if updated == value:
            break
        value = updated
    value = value.replace("⋅", "·").replace("•", "·").replace("−", "-")
    value = value.translate(_SUB_TRANS).translate(_SUP_TRANS)
    value = re.sub(r"_\{(\d+(?:\.\d+)?)\}", r"\1", value)
    value = re.sub(r"_(\d)", r"\1", value)
    return value.strip()


def parse_formula_counts(formula):
    """Parse a chemical formula (with nested (), [] and ·nH2O hydrates) into element counts."""
    cleaned = _strip_tex_wrappers(formula)
    cleaned = re.sub(r"\s+", "", cleaned)
    # Remove physical state suffix if present, e.g., (s), (l), (g), (aq).
    cleaned = re.sub(r"\((?:s|l|g|aq)\)$", "", cleaned)
    # Remove explicit ionic charge suffix (mass is unaffected).
    cleaned = re.sub(r"\^\{?\d*[+-]\}?$", "", cleaned)
    if not cleaned:
        return None
    total = {}
    for segment in re.split(r"[·*]", cleaned):
        if not segment:
            return None
        lead = re.match(r"^(\d+(?:/\d+|\.\d+)?)(.*)$", segment)
        if lead:
            coeff_text, body = lead.group(1), lead.group(2)
            try:
                segment_mult = float(Fraction(coeff_text)) if "/" in coeff_text else float(coeff_text)
            except (ValueError, ZeroDivisionError):
                return None
        else:
            segment_mult, body = 1.0, segment
        if not body:
            return None
        stack = [{}]
        brackets = []
        i = 0
        n = len(body)
        while i < n:
            ch = body[i]
            if ch in "([":
                stack.append({})
                brackets.append(")" if ch == "(" else "]")
                i += 1
            elif ch in ")]":
                if not brackets or brackets[-1] != ch:
                    return None
                brackets.pop()
                group = stack.pop()
                i += 1
                num = re.match(r"\d+(?:\.\d+)?", body[i:])
                mult = float(num.group(0)) if num else 1.0
                if num:
                    i += len(num.group(0))
                if not group:
                    return None
                for el, cnt in group.items():
                    stack[-1][el] = stack[-1].get(el, 0.0) + cnt * mult
            elif "A" <= ch <= "Z":
                sym = ch
                if i + 1 < n and "a" <= body[i + 1] <= "z":
                    two = ch + body[i + 1]
                    if two in ELEMENT_SYMBOLS:
                        sym = two
                        i += 2
                    elif ch in ELEMENT_SYMBOLS:
                        i += 1
                    else:
                        return None
                else:
                    if ch not in ELEMENT_SYMBOLS:
                        return None
                    i += 1
                num = re.match(r"\d+(?:\.\d+)?", body[i:])
                cnt = float(num.group(0)) if num else 1.0
                if num:
                    i += len(num.group(0))
                stack[-1][sym] = stack[-1].get(sym, 0.0) + cnt
            else:
                return None
        if brackets or len(stack) != 1 or not stack[0]:
            return None
        for el, cnt in stack[0].items():
            total[el] = total.get(el, 0.0) + cnt * segment_mult
    return total or None


def formula_molar_mass(formula, weights=None):
    """Return theoretical molar mass (g/mol) for a chemical formula, or None if invalid."""
    counts = parse_formula_counts(formula)
    if not counts:
        return None
    table = ATOMIC_WEIGHTS if weights is None else {**ATOMIC_WEIGHTS, **weights}
    return sum(cnt * table[el] for el, cnt in counts.items())


def is_chemical_species(token, *, require_structure=False):
    """Return True if token is a valid chemical formula/ion (with optional stoichiometric prefix)."""
    raw = _strip_tex_wrappers(token).strip()
    if not raw:
        return False
    # Strip trailing gas/precipitate arrows or state markers.
    raw = re.sub(r"[↑↓]+$", "", raw)
    raw = re.sub(r"\((?:s|l|g|aq)\)$", "", raw)
    # Strip trailing ion charge (explicit ^ or bare charge like Al3+, SO4^2-, OH-, Fe2+).
    charge = ""
    if m := re.search(r"\^\{?(\d*[+-])\}?$", raw):
        charge = m.group(1)
        core = raw[:m.start()]
    elif m := re.search(r"(\d*[+-])$", raw):
        charge = m.group(1)
        core = raw[:m.start()]
        # If core is empty or ends with non-alnum/bracket, not a valid ion.
        if not core or core[-1] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789)]":
            return False
    else:
        core = raw
    # Strip optional leading stoichiometric coefficient.
    core_no_coeff = re.sub(r"^\d+", "", core)
    counts = parse_formula_counts(core_no_coeff)
    if not counts:
        return False
    if not require_structure:
        return True
    # Require a multi-element formula, multi-atom formula, bracketed formula, or explicit charge.
    if charge or len(counts) >= 2 or "(" in core_no_coeff or "[" in core_no_coeff or "·" in core_no_coeff:
        return True
    total_atoms = sum(counts.values())
    if total_atoms >= 2:
        sym = next(iter(counts))
        return len(sym) == 2 or core_no_coeff in _HOMONUCLEAR_SINGLE
    return False


# --- Formatting bare ASCII chemistry/science tokens in rubric text ---

_SCI_NOTATION = re.compile(
    r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)\s*([×xX*])\s*10\s*\^\s*\{?([-−+]?\d+)\}?(?![A-Za-z0-9])"
)
_TEN_POWER = re.compile(r"(?<![A-Za-z0-9.])10\s*\^\s*\{?([-−+]?\d+)\}?(?![A-Za-z0-9])")
_UNIT_POWER = re.compile(
    r"(?<![A-Za-z])((?:kJ|J|mol|L|mL|g|kg|cm|mm|m|s|Pa|kPa|MPa|atm|K|V|A|Ω)"
    r"(?:\s*[·⋅/]\s*(?:kJ|J|mol|L|mL|g|kg|cm|mm|m|s|Pa|kPa|MPa|atm|K|V|A|Ω)"
    r"(?:\s*\^\s*\{?[-−+]?\d+\}?)?|\s*\^\s*\{?[-−+]?\d+\}?)+)(?![A-Za-z0-9])"
)
_CHEM_CONST = re.compile(
    r"(?<![A-Za-z0-9_])(K(?:_?\{?(?:sp|p\d*|a\d*|b\d*|w|h|c)\}?)?|Δ[HGSE]_?\d+|sp[23](?:d[2]?)?)(?![A-Za-z0-9_])"
)
# Match candidate chemical formulas/ions (optionally with leading stoichiometric integer).
_CHEM_CANDIDATE = re.compile(
    r"(?<![A-Za-z0-9_.])"
    r"(\d*(?:[A-Z][a-z]?\d*|\([A-Za-z0-9]+\)\d*|\[[A-Za-z0-9()]+\]\d*)+"
    r"(?:·\d*(?:[A-Z][a-z]?\d*|\([A-Za-z0-9]+\)\d*)+)*"
    r"(?:\^\{?\d*[+-]\}?|\d*[+-](?![A-Za-z0-9(\[]))?)"
)


def _formula_to_tex(token):
    """Convert a bare ASCII chemical formula/ion token to TeX \\(...\\), or return None if not applicable."""
    # Ignore pure letters with no digits and no charge (e.g., DNA, ATP, pH, In, No, As, He).
    if not re.search(r"[\d+-]", token):
        return None
    # Split optional leading stoichiometric coefficient.
    lead_m = re.match(r"^(\d+)(.*)$", token)
    lead, body = (lead_m.group(1), lead_m.group(2)) if lead_m else ("", token)
    if not body or not re.search(r"[\d+-]", body):
        return None

    # Extract charge suffix.
    charge = ""
    if m := re.search(r"\^\{?(\d*[+-])\}?$", body):
        charge = m.group(1)
        core = body[:m.start()]
    elif m := re.search(r"(\d*[+-])$", body):
        raw_charge = m.group(1)
        prefix = body[:m.start()]
        if not prefix:
            return None
        # Distinguish monatomic ion (Al3+, Fe2+, S2-) vs polyatomic ion (NH4+, MnO4-, SO42-, [Al(OH)4]-).
        if prefix.endswith("]"):
            charge = raw_charge
            core = prefix
        else:
            # Check how many elements are in prefix.
            prefix_counts = parse_formula_counts(prefix)
            if prefix_counts and len(prefix_counts) == 1 and not re.search(r"\d", prefix):
                # Monatomic ion like Al3+, Fe2+, H+, Cl-, O2-.
                charge = raw_charge
                core = prefix
            else:
                # Polyatomic ion without explicit '^'.
                digits = raw_charge[:-1]
                sign = raw_charge[-1]
                if len(digits) == 0:
                    charge = sign
                    core = prefix
                elif len(digits) == 1:
                    # e.g., NH4+, NO3-, MnO4-, HCO3- -> digit belongs to last atom subscript, charge is +/-.
                    core = prefix + digits
                    charge = sign
                else:
                    # e.g., SO42-, CO32-, PO43-, Cr2O72- -> last digit is charge magnitude.
                    core = prefix + digits[:-1]
                    charge = digits[-1] + sign
    else:
        core = body

    counts = parse_formula_counts(core)
    if not counts:
        return None

    # Guard against non-chemical identifiers like Q15, A1, B2, F1, C3, T2.
    if not charge and len(counts) == 1 and "(" not in core and "[" not in core and "·" not in core:
        sym = next(iter(counts))
        if len(sym) == 1 and core not in _HOMONUCLEAR_SINGLE:
            return None
        if sum(counts.values()) == 1:
            return None

    # Convert core subscripts and hydrate dots into TeX inside \mathrm{...}.
    segments = []
    for seg in core.split("·"):
        seg_lead_m = re.match(r"^(\d+)(.*)$", seg)
        seg_lead, seg_body = (seg_lead_m.group(1), seg_lead_m.group(2)) if seg_lead_m else ("", seg)
        tex_body = re.sub(r"([A-Za-z)\]])(\d+)", lambda x: f"{x.group(1)}_{{{x.group(2)}}}" if len(x.group(2)) > 1 else f"{x.group(1)}_{x.group(2)}", seg_body)
        segments.append(seg_lead + tex_body)
    tex_core = r"\cdot ".join(segments)
    if charge:
        charge_tex = f"^{{{charge}}}" if len(charge) > 1 else f"^{charge}"
        return r"\(" + lead + r"\mathrm{" + tex_core + "}" + charge_tex + r"\)"
    return r"\(" + lead + r"\mathrm{" + tex_core + "}" + r"\)"


def _format_plain_segment(segment):
    # 1. Convert single-dollar inline math $...$ to \(...\) if present.
    def _dollar_to_paren(m):
        return r"\(" + m.group(1) + r"\)"

    segment = re.sub(r"(?<!\\)\$([^$\n]+?)\$", _dollar_to_paren, segment)

    def _transform_non_math(text):
        # Scientific notation: 2.7×10^-3 -> \(2.7\times 10^{-3}\)
        text = _SCI_NOTATION.sub(
            lambda m: r"\(" + m.group(1) + r"\times 10^{" + m.group(3).replace("−", "-") + r"}\)",
            text,
        )
        # Standalone 10^-14
        def _ten_pow(m):
            return r"\(10^{" + m.group(1).replace("−", "-") + r"}\)"

        # Process outside any newly created \(...\) spans.
        def _apply_outside(src, fn):
            out = []
            pos = 0
            for m in re.finditer(r"\\\(.*?\\\)", src, re.S):
                out.append(fn(src[pos:m.start()]))
                out.append(m.group(0))
                pos = m.end()
            out.append(fn(src[pos:]))
            return "".join(out)

        text = _apply_outside(text, lambda s: _TEN_POWER.sub(_ten_pow, s))

        # Units with caret powers: mol·L^-1, kJ·mol^-1, s^-1
        def _unit_sub(m):
            raw_unit = m.group(1)
            if "^" not in raw_unit:
                return raw_unit
            tex = raw_unit.replace("−", "-")
            tex = re.sub(r"([A-Za-zΩ]+)", r"\\mathrm{\1}", tex)
            tex = re.sub(r"\s*[·⋅]\s*", r"\\cdot ", tex)
            tex = re.sub(r"\s*\^\s*\{?([-+]?\d+)\}?", r"^{\1}", tex)
            return r"\(" + tex + r"\)"

        text = _apply_outside(text, lambda s: _UNIT_POWER.sub(_unit_sub, s))

        # Chemistry equilibrium / thermo / hybridization symbols: Kp1, Ksp, Ka1, ΔH1, sp2, sp3
        def _const_sub(m):
            tok = m.group(1)
            if tok == "K":
                return tok
            if tok.startswith("sp"):
                tex = re.sub(r"(\d+)", r"^{\1}", tok)
                return r"\(\mathrm{" + tex + r"}\)"
            if tok.startswith("Δ"):
                letter = tok[1]
                idx = tok[2:].lstrip("_")
                return r"\(\Delta " + letter + (f"_{{{idx}}}" if len(idx) > 1 else f"_{idx}") + r"\)"
            sub = tok[1:].lstrip("_").strip("{}")
            if not sub:
                return tok
            if sub in ("sp", "w", "h", "c"):
                return r"\(K_{\mathrm{" + sub + r"}}\)"
            return r"\(K_{" + sub + r"}\)"

        text = _apply_outside(text, lambda s: _CHEM_CONST.sub(_const_sub, s))

        # Bare chemical formulas & ions: H2O2, Al3+, Co3O4, Fe(OH)3, [Al(OH)4]-, SO4^2-
        def _chem_sub(m):
            tok = m.group(1)
            converted = _formula_to_tex(tok)
            return converted if converted is not None else tok

        text = _apply_outside(text, lambda s: _CHEM_CANDIDATE.sub(_chem_sub, s))
        return text

    out = []
    pos = 0
    for m in re.finditer(r"\\\(.*?\\\)", segment, re.S):
        out.append(_transform_non_math(segment[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_transform_non_math(segment[pos:]))
    return "".join(out)


def format_science_rubric(text):
    """Idempotently wrap bare ASCII chemistry/science formulas, powers, and constants in TeX."""
    if not text:
        return text
    return _format_plain_segment(text)
