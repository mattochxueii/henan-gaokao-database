import bootstrap
from mathgen.generate import FAMILIES, draft, add_options
from mathgen.quality import verify

for name in FAMILIES:
    try:
        row = add_options(draft(name, 37), 38)
        result = verify(row)
        print(
            name,
            result["passed"],
            result["proposal_matches_independent_solution"],
            result["program_checks"],
        )
    except Exception as error:
        print(name, type(error).__name__, str(error))
