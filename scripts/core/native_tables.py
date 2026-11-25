
"""Editable Chinese three-line tables shared by science PDF and DOCX."""
from gaokao import require


def normalize_table(table):
    require(isinstance(table,dict) and set(table)<={"headers","rows","caption"} and
            "headers" in table and "rows" in table,"表格须包含 headers 与 rows")
    headers,rows=table["headers"],table["rows"]
    require(isinstance(headers,list) and 2<=len(headers)<=8 and isinstance(rows,list)
            and 1<=len(rows)<=20,"表格须为2～8列，1～20行数据")
    require(all(isinstance(row,list) and len(row)==len(headers) for row in rows),"表格列数不一致")
    require(all(isinstance(cell,str) and cell.strip() and len(cell)<=180 and "\n" not in cell
                for row in [headers,*rows] for cell in row),"表格单元格须为简短文本")
    require(len(set(headers))==len(headers),"表头重复")
    caption=table.get("caption","")
    require(isinstance(caption,str) and len(caption)<=140,"表题须为简短文本")
    return {"headers":headers,"rows":rows,**({"caption":caption} if caption else {})}


def pdf_table(table, paragraph, available_width):
    from reportlab.platypus import Table

    rows=[[paragraph(cell) for cell in row] for row in [table["headers"],*table["rows"]]]
    # A fixed total width gives short numeric cells a balanced, legible table.
    width = available_width*.76
    return Table(rows,colWidths=[width/len(rows[0])]*len(rows[0]),repeatRows=1,hAlign="CENTER",spaceAfter=7,style=[
        ("LINEABOVE",(0,0),(-1,0),.85,"#222222"),
        ("LINEBELOW",(0,0),(-1,0),.45,"#222222"),
        ("LINEBELOW",(0,-1),(-1,-1),.85,"#222222"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ])


def markdown_table(table):
    def line(cells):
        return "| "+" | ".join(v.replace("|",r"\|") for v in cells)+" |"
    header=table["headers"]
    return ["", *([table["caption"],""] if table.get("caption") else []),line(header),
            line(["---"]*len(header)),*(line(row) for row in table["rows"]),""]
