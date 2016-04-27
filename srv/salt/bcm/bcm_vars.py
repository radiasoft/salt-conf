#!/usr/bin/env python
from __future__ import print_function


def main(argv):
    assert len(argv) == 1, \
        'usage: bcm_vars pillars|grains|<file>.yml'
    prefix = argv[0]
    if prefix in ('grains', 'pillar'):
        a = _value_salt(prefix)
    else:
        a = _value_yaml(prefix)
    _print_value(*a)
    return 0


def _print_array(name, value, atype):
    print('declare -{} {}=('.format('A' if issubclass(atype, dict) else 'a', name))
    for k, v in value.items():
        print("[{}]='{}'".format(k, v))
    print(');')


def _print_value(prefix, value):
    assert isinstance(value, (dict, list)), \
        '{}: unable to handle type {}'.format(value, type(value))
    as_array = {}
    gen = value.items() if isinstance(value, dict) else zip(xrange(len(value)), value)
    for k, v in gen:
        pk = prefix + '_' + str(k)
        if isinstance(v, (dict, list)):
            _print_value(pk, v)
            # Only can print as_array if all values are scalar
            as_array = None
        else:
            v = _scalar(v)
            if as_array is not None:
                as_array[k] = v
            print("{}='{}';".format(pk, v))
    if as_array is not None:
        _print_array(prefix, as_array, type(value))


def _scalar(v):
    if isinstance(v, bool):
        return '1' if v else ''
    elif v is None:
        return ''
    # Might be a float or int so convert now
    return str(v)


def _value_salt(prefix):
    import salt.client
    c = salt.client.Caller()
    return prefix, c.function(prefix + '.items')


def _value_yaml(filename):
    import re
    m = re.search(r'(\w+)\.yml$', filename)
    assert m, \
        '{}: not YAML or pillars or grains'.format(filename)
    import yaml
    return m.group(1), yaml.load(open(filename))


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
