"""
All functions in this module have been copied from the toolz library.
For more information, see: https://github.com/pytoolz/toolz/
"""
import collections
import itertools
import operator


def getter(index):
    if isinstance(index, list):
        if len(index) == 1:
            index = index[0]
            return lambda x: (x[index],)
        elif index:
            return operator.itemgetter(*index)
        else:
            return lambda x: ()
    else:
        return operator.itemgetter(index)


def groupby(key, seq):
    """ Group a collection by a key function

    >>> names = ['Alice', 'Bob', 'Charlie', 'Dan', 'Edith', 'Frank']
    >>> groupby(len, names)  # doctest: +SKIP
    {3: ['Bob', 'Dan'], 5: ['Alice', 'Edith', 'Frank'], 7: ['Charlie']}

    >>> iseven = lambda x: x % 2 == 0
    >>> groupby(iseven, [1, 2, 3, 4, 5, 6, 7, 8])  # doctest: +SKIP
    {False: [1, 3, 5, 7], True: [2, 4, 6, 8]}

    Non-callable keys imply grouping on a member.

    >>> groupby('gender', [{'name': 'Alice', 'gender': 'F'},
    ...                    {'name': 'Bob', 'gender': 'M'},
    ...                    {'name': 'Charlie', 'gender': 'M'}]) # doctest:+SKIP
    {'F': [{'gender': 'F', 'name': 'Alice'}],
     'M': [{'gender': 'M', 'name': 'Bob'},
           {'gender': 'M', 'name': 'Charlie'}]}

    See Also:
        countby
    """
    if not callable(key):
        key = getter(key)
    d = collections.defaultdict(lambda: [].append)
    for item in seq:
        d[key(item)](item)
    rv = {}
    for k, v in d.items():
        rv[k] = v.__self__
    return rv


def concat(seqs):
    """ Concatenate zero or more iterables, any of which may be infinite.

    An infinite sequence will prevent the rest of the arguments from
    being included.

    We use chain.from_iterable rather than ``chain(*seqs)`` so that seqs
    can be a generator.

    >>> list(concat([[], [1], [2, 3]]))
    [1, 2, 3]

    See also:
        itertools.chain.from_iterable  equivalent
    """
    return itertools.chain.from_iterable(seqs)


def concatv(*seqs):
    """ Variadic version of concat

    >>> list(concatv([], ["a"], ["b", "c"]))
    ['a', 'b', 'c']

    See also:
        itertools.chain
    """
    return concat(seqs)
