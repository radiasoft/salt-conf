#!py
# -*-python-*-
#
# State tree files are related to each other. This module
# allows you to organize them that way using pillars
# to drive the state tree files to be run.
#
def run():
    """Sort pillar ``state_trees`` topologically and return as top trees.

    state_trees are the state "state files" to be executed
    as defined by the pillar files. Since pillar.stack merges
    hashes, we end up with something like::

        state_trees:
          utilities: []
          jupyterhub: [ utilities ]

    jupyterhub depends on utilities so we know the order
    to execute the state files in so we don't need to double
    specify in the salt and pillar files. salt trees are
    independent and invoked by the pillar.stack for the minion.
    """
    todo = {}
    for k, v in __pillar__['state_trees'].iteritems():
        todo[k] = v

    return {
        'base': {
            '*': _toposort(todo)
        },
    }


def _toposort(todo):
    """Topological sort dependencies"""
    done = {}
    res = []

    def _visit(node, parent=None):
        if node in done:
            assert done[node], '{}: not a DAG'.format(node)
            return
        done[node] = False
        if not node in todo:
            raise ValueError('"{}" is a dependency of "{}" so must be included'.format(node, parent))
        for edge in todo[node]:
            _visit(edge, node)
        done[node] = True
        res.append(node)

    nodes = sorted(todo.keys())
    for n in nodes:
        if not n in done:
            _visit(n)
    print res
    return res
