import yaml
import salt.client
c = salt.client.Caller()
x = c.function('pillar.items')
#print x
def dump(values, prefix='pillar'):
    if isinstance(values, dict):
        a = {}
        for k, v in values.items():
            pk = prefix + '_' + k
            if isinstance(v, (dict, list)):
                dump(v, pk)
                a = None
            else:
                if isinstance(v, bool):
                    v = '1' if v else ''
                elif v is None:
                    v = ''
                if a is not None:
                    a[k] = v
                print "{}='{}'".format(pk, v)
        if a is not None:
            res = '{}=('.format(prefix)
            for k, v in a.items():
                res += "\n    [{}]='{}'".format(k, v)
            print(res + '\n)')
    elif isinstance(values, list):
        a=list()
        for k, v in zip(xrange(len(values)), values):
            pk = prefix + '_' + str(k)
            if isinstance(v, (dict, list)):
                dump(v, pk)
                a = None
            else:
                if isinstance(v, bool):
                    v = '1' if v else ''
                elif v is None:
                    v = ''
                if a is not None:
                    a.append(v)
                print "{}='{}'".format(pk, v)
        if a is not None:
            res = '{}=('.format(prefix)
            for v in a:
                res += "'{}' ".format(v)
            print(res + ')')
    else:
        raise AssertionError('{}: unable to handle type {}'.format(values, type(values)))

dump(x)
