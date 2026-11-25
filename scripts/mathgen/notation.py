"""Student-facing algebra notation; no AST dumps, Boolean formulas or fallback strings."""

import ast
from collections import Counter
from gaokao import require

VERSION = "school-notation-v1"


def latex(source):
    require(isinstance(source, str) and len(source) <= 1400, "公式长度无效")
    root = ast.parse(source, mode="eval").body
    require(len(list(ast.walk(root))) <= 220, "公式过长")

    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return str(node.value), 100
        if isinstance(node, ast.Name):
            require(
                node.id.isalpha() and len(node.id) <= 2 or node.id in ("pi", "oo"),
                "未声明的公式记号",
            )
            return {"pi": r"\pi", "oo": r"\infty", "I": "i", "E": "e"}.get(
                node.id, node.id
            ), 100
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value, p = walk(node.operand)
            return ("-" if isinstance(node.op, ast.USub) else "+") + (
                "(" + value + ")" if p < 30 else value
            ), 30
        if isinstance(node, ast.BinOp):
            left, lp = walk(node.left)
            right, rp = walk(node.right)
            if isinstance(node.op, ast.Div):
                return r"\frac{" + left + "}{" + right + "}", 70
            if isinstance(node.op, ast.Pow):
                if lp < 80:
                    left = r"\left(" + left + r"\right)"
                return left + "^{" + right + "}", 80
            if isinstance(node.op, ast.Mult):
                nodes = []

                def flatten(n):
                    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
                        flatten(n.left)
                        flatten(n.right)
                    else:
                        nodes.append(n)

                flatten(node)
                rendered = [walk(n) for n in nodes]
                terms = []
                i = 0
                while i < len(rendered):
                    text, p = rendered[i]
                    count = 1
                    while (
                        i + count < len(rendered)
                        and rendered[i + count] == (text, p)
                        and text.isalpha()
                    ):
                        count += 1
                    if p < 50 and not (text.startswith("-") and text[1:].isdigit()):
                        text = r"\left(" + text + r"\right)"
                    if count > 1:
                        text += "{" + str(count) + "}"
                    if count > 1:
                        text = text.rsplit("{", 1)[0] + "^{" + str(count) + "}"
                    if terms and terms[-1][-1:].isdigit() and text[:1].isdigit():
                        terms.append(r"\cdot ")
                    terms.append(text)
                    i += count
                return "".join(terms), 50
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if lp < 20:
                    left = "(" + left + ")"
                if rp < 20 or isinstance(node.op, ast.Sub) and rp == 20:
                    right = r"\left(" + right + r"\right)"
                return left + ("+" if isinstance(node.op, ast.Add) else "-") + right, 20
            raise ValueError("考生公式禁止程序取模等运算，改写为中文条件")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            name = node.func.id
            args = [walk(a)[0] for a in node.args]
            require(1 <= len(args) <= 2, "函数参数无效")
            if name in ("u", "a", "b", "c", "S", "T") and len(args) == 1:
                return name + "_{" + args[0] + "}", 100
            if name == "sqrt":
                return r"\sqrt{" + args[0] + "}", 100
            if name == "factorial":
                return (
                    "(" + args[0] + ")" if not args[0].isalnum() else args[0]
                ) + "!", 90
            if name == "abs":
                return r"\left|" + args[0] + r"\right|", 100
            if name == "binomial":
                return r"\mathrm{C}_{" + args[0] + "}^{" + args[1] + "}", 100
            if name == "exp":
                return "e^{" + args[0] + "}", 100
            require(name in ("sin", "cos", "tan", "log"), "公式函数不受支持")
            return {"log": r"\ln", "sin": r"\sin", "cos": r"\cos", "tan": r"\tan"}[
                name
            ] + r"\left(" + args[0] + r"\right)", 100
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, _ = walk(node.left)
            right, _ = walk(node.comparators[0])
            op = {
                ast.Eq: "=",
                ast.NotEq: r"\ne ",
                ast.Lt: "<",
                ast.LtE: r"\leq ",
                ast.Gt: ">",
                ast.GtE: r"\geq ",
            }.get(type(node.ops[0]))
            require(op, "不支持的关系")
            return left + op + right, 10
        raise ValueError("不能转成高中规范记号的表达式，拒绝输出")

    return walk(root)[0]
