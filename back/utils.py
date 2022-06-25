import regex
from collections import Counter
from typing import List, Tuple


def get_id(uri: str) -> str:
    return regex.search(r"(?!spotify)?+(?!.com\/\w+\/)?(?!:\w+:)?[a-z|A-Z|\d]{20,}", uri)[0]


def remove_duplicates(items: List) -> List:
    return list(dict.fromkeys(items))


def difference(parent: List, child: List) -> Tuple[List[str], List[str]]:
    c_parent = Counter(parent)
    c_child = Counter(child)

    c_total = {}

    for c in c_child.keys():
        if c_parent.keys().__contains__(c) and c_child[c] != c_parent[c]:
            c_total[c] = c_child[c] - c_parent[c]
        else:
            c_total[c] = c_child[c]

    for c in c_parent.keys():
        if not c_total.keys().__contains__(c):
            c_total[c] = -c_parent[c]

    to_add = []
    to_remove = []
    if len(c_total) > 0:
        for d in c_total.keys():
            count = c_total[d]
            if count > 0:
                for i in range(0, count):
                    to_add.append(d)
            elif count < 0:
                for i in range(0, abs(count)):
                    to_remove.append(d)

    return to_add, to_remove
