import re
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# === Token ===
class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value

    def to_dict(self):
        return {"type": self.type, "value": self.value}


# === Lexer ===
class Lexer:
    def __init__(self):
        self.token_spec = [
            ('INCLUDE', r'#\s*include\s*<[^>]+>'),
            ('KEYWORD', r'\b(int|float|char|double|long|short|void|return|if|else|for|while|do|printf|scanf|main)\b'),
            ('ID',      r'\b[a-zA-Z_]\w*\b'),
            ('NUM',     r'\b\d+(\.\d+)?\b'),
            ('STRING',  r'".*?"'),
            ('OP',      r'[=+\-*/<>!]'),
            ('LPAREN',  r'\('),
            ('RPAREN',  r'\)'),
            ('LBRACE',  r'\{'),
            ('RBRACE',  r'\}'),
            ('LBRACKET',r'\['),       
            ('RBRACKET',r'\]'),         
            ('DELIM',   r'[;,]'),
            ('SKIP',    r'[ \t\n]+'),
            ('MISMATCH', r'.'),
        ]

    def tokenize(self, code):
        tokens = []
        pattern = '|'.join(f'(?P<{name}>{regex})' for name, regex in self.token_spec)

        for mo in re.finditer(pattern, code):
            kind = mo.lastgroup
            value = mo.group()
            if kind == 'SKIP':
                continue
            elif kind == 'MISMATCH':
                raise RuntimeError(f"Unexpected character: {value}")
            tokens.append(Token(kind, value))
        return tokens


# === Parser ===
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.ast = []
        self.errors = []

    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def match(self, type_, value=None):
        token = self.current()
        if token and token.type == type_ and (value is None or token.value == value):
            self.pos += 1
            return token
        return None

    def parse(self):
        while self.pos < len(self.tokens):
            token = self.current()
            if token.type == 'INCLUDE':
                self.ast.append(('include', token.value))
                self.pos += 1
            elif token.type == 'KEYWORD':
                if self.lookahead_is_function():
                    self.function_definition()
                elif token.value == 'printf':
                    self.printf_statement()
                else:
                    self.statement()
            else:
                self.statement()
        return self.ast, self.errors

    def lookahead_is_function(self):
        return (self.pos + 1 < len(self.tokens) and
                self.tokens[self.pos + 1].type in {'ID', 'KEYWORD'} and
                self.tokens[self.pos + 1].value == 'main')

    def function_definition(self):
        ret_type = self.match('KEYWORD')
        func_name = self.match('KEYWORD') or self.match('ID')
        self.match('LPAREN')
        self.match('RPAREN')
        if not self.match('LBRACE'):
            self.errors.append("Syntax Error: Missing '{' in function")
            return

        while self.current() and self.current().type != 'RBRACE':
            token = self.current()
            if token.type == 'KEYWORD' and token.value == 'printf':
                self.printf_statement()
            else:
                self.statement()

        if not self.match('RBRACE'):
            self.errors.append("Syntax Error: Missing '}' in function")

    def statement(self):
        type_tok = self.match('KEYWORD')
        id_tok = self.match('ID')
        if not (type_tok and id_tok):
            self.errors.append("Syntax Error: Invalid declaration")
            self.pos += 1
            return

        # Check for array declaration
        if self.match('LBRACKET'):
            size_tok = self.match('NUM')
            if not size_tok or not self.match('RBRACKET'):
                self.errors.append("Syntax Error: Invalid array declaration")
                return
            self.ast.append(('declare_array', type_tok.value, id_tok.value, size_tok.value))
        else:
            self.ast.append(('declare', type_tok.value, id_tok.value))

        if self.match('OP', '='):
            expr = self.expression()
            if not expr:
                self.errors.append("Syntax Error: Invalid expression")
                return
            self.ast.append(('assign_expr', type_tok.value, id_tok.value, expr))

        if not self.match('DELIM'):
            self.errors.append("Syntax Error: Missing semicolon")

    def printf_statement(self):
        self.match('KEYWORD', 'printf')
        if not self.match('LPAREN'):
            self.errors.append("Syntax Error: Expected '('")
            return
        str_tok = self.match('STRING')
        if not str_tok:
            self.errors.append("Syntax Error: Expected string in printf")
            return
        if not self.match('RPAREN'):
            self.errors.append("Syntax Error: Expected ')' in printf")
            return
        if not self.match('DELIM'):
            self.errors.append("Syntax Error: Missing semicolon after printf")
            return
        self.ast.append(('printf', str_tok.value))

    def expression(self):
        return self.add_sub()

    def add_sub(self):
        node = self.mul_div()
        while True:
            op_tok = self.match('OP', '+') or self.match('OP', '-')
            if op_tok:
                right = self.mul_div()
                node = ('binop', op_tok.value, node, right)
            else:
                break
        return node

    def mul_div(self):
        node = self.factor()
        while True:
            op_tok = self.match('OP', '*') or self.match('OP', '/')
            if op_tok:
                right = self.factor()
                node = ('binop', op_tok.value, node, right)
            else:
                break
        return node

    def factor(self):
        tok = self.current()
        if tok and tok.type in {'NUM', 'ID'}:
            self.pos += 1
            return ('leaf', tok.value)
        elif tok and tok.type == 'LPAREN':
            self.match('LPAREN')
            expr = self.expression()
            self.match('RPAREN')
            return expr
        return None


# === Semantic Analyzer ===
class SemanticAnalyzer:
    def __init__(self, ast):
        self.ast = ast
        self.symbols = set()
        self.errors = []

    def analyze(self):
        for stmt in self.ast:
            if stmt[0] in {'declare', 'declare_array'}:
                _, _, name = stmt[:3]
                if name in self.symbols:
                    self.errors.append(f"Semantic Error: '{name}' redeclared")
                else:
                    self.symbols.add(name)
            elif stmt[0] == 'assign_expr':
                _, _, name, _ = stmt
                if name not in self.symbols:
                    self.errors.append(f"Semantic Error: Undeclared variable '{name}'")
        return self.errors


# === Intermediate Code Generator ===
class ICG:
    def __init__(self, ast):
        self.ast = ast
        self.code = []
        self.temp_count = 0

    def new_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def generate(self):
        for stmt in self.ast:
            if stmt[0] == 'include':
                self.code.append(stmt[1])
            elif stmt[0] == 'declare':
                _, typ, name = stmt
                self.code.append(f"{typ} {name}")
            elif stmt[0] == 'declare_array':
                _, typ, name, size = stmt
                self.code.append(f"{typ} {name}[{size}]")
            elif stmt[0] == 'assign_expr':
                _, _, name, expr = stmt
                result = self.handle_expr(expr)
                self.code.append(f"{name} = {result}")
            elif stmt[0] == 'printf':
                _, string_value = stmt
                self.code.append(f"print {string_value}")
        return self.code

    def handle_expr(self, node):
        if node[0] == 'leaf':
            return node[1]
        elif node[0] == 'binop':
            _, op, left, right = node
            l = self.handle_expr(left)
            r = self.handle_expr(right)
            temp = self.new_temp()
            self.code.append(f"{temp} = {l} {op} {r}")
            return temp


# === Flask Routes ===
@app.route('/')
def index():
    return render_template("index.html")

@app.route('/analyze', methods=['POST'])
def analyze():
    code = request.json.get('code', '')

    try:
        lexer = Lexer()
        tokens = lexer.tokenize(code)

        parser = Parser(tokens)
        ast, syntax_errors = parser.parse()

        semantic = SemanticAnalyzer(ast)
        semantic_errors = semantic.analyze()

        icg = ICG(ast)
        intermediate_code = icg.generate()

        return jsonify({
            "tokens": [t.to_dict() for t in tokens],
            "syntaxErrors": syntax_errors,
            "semanticErrors": semantic_errors,
            "intermediateCode": intermediate_code
        })

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)

