from pycparser import c_ast, parse_file
from os import path

class FuncCallVisitor(c_ast.NodeVisitor):
    def __init__(self):
        self.func_calls = set()
        self.scopes = []

    def visit_scope(self, node):
        self.scopes.append({})
        self.generic_visit(node)
        self.scopes.pop()

    def visit_FileAST(self, node):
        self.visit_scope(node)

    def visit_Compound(self, node):
        self.visit_scope(node)

    def visit_For(self, node):
        self.visit_scope(node)

    # -------- potentially useless as the C syntax disallows decls inside whiles, ifs, do whiles and swithes
    # TODO check ça pour etre sur (https://en.cppreference.com/w/c/language/scope)
    def visit_While(self, node):
        self.visit_scope(node)

    def visit_DoWhile(self, node):
        self.visit_scope(node)

    def visit_If(self, node):
        self.visit_scope(node)

    def visit_Switch(self, node):
        self.visit_scope(node)
    # -------- potentially useless as the C syntax disallows decls inside whiles, ifs, do whiles and swithes

    def visit_PtrDecl(self, node):
        if isinstance(node.type, c_ast.FuncDecl):
            # print(f"{node} called at {node.coord}")
            # TODO peut it se faire overwriter et le scope ne sera pas mis à jour ?
            self.scopes[-1][node.type.type.declname] = True

        self.generic_visit(node)

    def visit_FuncCall(self, node):
        # this also handles the case where a function returns a function that is immediately called
        found = False
        if type(node.name.name) is str:
            for s in reversed(self.scopes):
                if node.name.name in s:
                    found = True
                    # ignore function pointer calls as we can't always find their original function names
                    # print(f"\tIGNORED: {node.name.name} called at {node.name.coord}")
                    break

        if not found:
            self.func_calls.add(node.name.name)

        self.generic_visit(node)


class FuncCallParser():
    def __init__(self, source_file):
        self.source_file = source_file
        self.__include_path = path.join(path.dirname(__file__), "utils/fake_libc_include")

    def parse(self):
        try:
            ast = parse_file(self.source_file, use_cpp=True, cpp_path="gcc",
                             cpp_args=['-E', f'-I{self.__include_path}'])
            ast.show()
            v = FuncCallVisitor()
            v.visit(ast)

            return v.func_calls
        except Exception:
            print(f"Error parsing file '{source_file}' to retreive function calls")
            return None
