
"""Print exact page counts without editing or rerendering completed exam PDFs."""
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import cm


def calculation_corners(canvas, left, bottom, width, top):
    canvas.saveState()
    canvas.setStrokeGray(.84)
    canvas.setLineWidth(.35)
    for x, direction in ((left,1),(left+width,-1)):
        for y, leg in ((bottom,1),(top,-1)):
            canvas.lines([(x,y,x+9*direction,y),(x,y,x,y+6*leg)])
    canvas.restoreState()


class ExamPages(Canvas):
    def __init__(self,*args,footer_font,**kwargs):
        super().__init__(*args,**kwargs)
        self._footer_font=footer_font
        self._page_states=[]
        self.question_starts = []
        self.calculation_areas = []

    def showPage(self):
        for x,bottom,width,top,placement in self.calculation_areas:
            if self.question_starts == [placement["number"]] and bottom > 1.5*cm:
                placement["height_cm"] = round(placement["height_cm"]+(bottom-1.5*cm)/cm,2)
                bottom = 1.5*cm
            calculation_corners(self,x,bottom,width,top)
        self.question_starts.clear()
        self.calculation_areas.clear()
        self._page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        pages=len(self._page_states)
        for state in self._page_states:
            self.__dict__.update(state)
            self.setFont(self._footer_font,9)
            self.drawCentredString(self._pagesize[0]/2,22,f"第 {self._pageNumber} 页　共 {pages} 页")
            super().showPage()
        super().save()
