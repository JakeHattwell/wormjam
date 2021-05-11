# Copy Paste of classes from .github/tests/support/helper_classes
# and reaction string processing reaction from tsv_to_sbml script.

import csv
from pathlib import Path


# CONFIG
#
# Note: I recommend using this script from the command line and sending output to a file

rxn_sbtab_name = "Reaction-SBtab.tsv"
rxn_path = Path("curation") / rxn_sbtab_name

# Helper function/classes


def react_proc(rxn):
    r, p = rxn.split("<=>")

    def quick(frag):
        frag = frag.split("+")
        frag = [i.rstrip().lstrip() for i in frag]
        frag = [i.split(" ") for i in frag]
        return frag

    r = quick(r)
    p = quick(p)
    # packaging
    reactants = {
        (i[1] if len(i) == 2 else i[0]): (i[0] if len(i) == 2 else "1") for i in r
    }
    products = {
        (i[1] if len(i) == 2 else i[0]): (i[0] if len(i) == 2 else "1") for i in p
    }
    for d in [reactants, products]:
        for key, val in d.items():
            try:
                d[key] = str(float(val))
            except:
                pass

    return (reactants, products)


class SBtable:
    """Importable class for loading SBTab files\nConverts SBTab as nested dictionary.\n

    instance.data = Dictionary of entries in SBTab\n
    Each entry is a dictionary of the data associated with that entry, with column headers as keys.

        Arguments:
            xlsx {str} -- Path to SBTab file of interest.

        Keyword Arguments:
            headerRow {int} -- Excel row of the header information, (default: {2})
            mode {str} -- version of SBtable to load
    """

    def __init__(self, filename, headerRow=2):
        """Loads the SBTab file"""
        self.name = filename
        with open(filename, encoding="latin-1") as tsvfile:
            tsv = csv.reader(tsvfile, delimiter="\t")
            entries = []
            for row in tsv:
                if tsv.line_num == 1:  # row 1 - SBtab DocString
                    self.sbString = row[0]
                elif tsv.line_num == 2:  # row 2 - headers of the table
                    self.headers = row
                else:
                    entries.append(row)
            # define size of data
            self.cols = len(self.headers)
            self.rows = len(entries) + 2
            # create the nested dict object
            try:
                self.data = {
                    entry[0]: {
                        self.headers[i]: (
                            entry[i] if len(entry) >= len(self.headers) else ""
                        )
                        for i in range(1, len(self.headers))
                    }
                    for entry in entries
                }
                while "" in self.data:
                    self.data.pop("")
            except:
                print(self.name)
                print("tsv import failed. Aborting...")
                exit()
            # remove blank entries
        self.unused = [
            h for h in self.headers if all(self.data[a].get(h) == "" for a in self.data)
        ]


reactions = SBtable(rxn_path)
print(len(reactions.data))
for i in list(reactions.data.keys()):
    r, p = react_proc(reactions.data[i]["!ReactionFormula"])
    species = {**r, **p}
    for key in list(species.keys()):
        if key == "":
            species.pop(key)
    counts = {}
    for key in species:
        counts[key[-1]] = counts.get(key[-1], 0) + 1
    results = [
        i + " " + str(counts[i]) for i in sorted(counts, key=counts.get, reverse=True)
    ]
    if len(results) == 1:
        results = results[0][0]
    elif results[0].split(" ")[1] == results[1].split(" ")[1]:
        results = results[0].split(" ")[0] + results[1].split(" ")[0]
    else:
        results = results[0][0]
    print(i, results, sep="\t")
