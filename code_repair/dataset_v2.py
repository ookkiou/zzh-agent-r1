"""Versioned mutation additions; v0.1 conversion and execution contracts stay frozen."""
import ast
import copy

from .dataset import mutations, replace_at, walk_paths


def expanded_mutations(source):
    tree=ast.parse(source)
    result=list(mutations(source))
    seen={item['source'] for item in result}

    def emit(path,node,replacement,kind):
        changed=copy.deepcopy(tree)
        replace_at(changed,path,copy.deepcopy(replacement))
        changed=ast.fix_missing_locations(changed)
        text=ast.unparse(changed)+'\n'
        if text==source or text in seen:return
        located=tree
        line=column=0
        for part in path:
            located=located[part] if isinstance(part,int) else getattr(located,part)
            if hasattr(located,'lineno'):line,column=located.lineno,located.col_offset
        seen.add(text)
        result.append({'source':text,'bug_type':kind,'mutation':{'ast_path':list(path),
            'line':line,'column':column,'before':ast.dump(node),'after':ast.dump(replacement),
            'single_location':True}})

    operators={ast.Add:ast.Sub,ast.Sub:ast.Add,ast.Mult:ast.Add,
               ast.FloorDiv:ast.Mod,ast.Mod:ast.FloorDiv,ast.Pow:ast.Mult}
    for path,node in walk_paths(tree):
        if isinstance(node,(ast.BinOp,ast.AugAssign)) and type(node.op) in operators:
            emit(path+('op',),node.op,operators[type(node.op)](),'arithmetic')
        if isinstance(node,ast.BoolOp):
            replacement=ast.Or() if isinstance(node.op,ast.And) else ast.And()
            emit(path+('op',),node.op,replacement,'boolean_logic')
        if isinstance(node,ast.Constant) and type(node.value) is int and -1<=node.value<=10:
            for value in (node.value-1,node.value+1):
                emit(path,node,ast.Constant(value=value),'numeric_constant')
    return result
