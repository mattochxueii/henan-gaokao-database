
"""Print exact page counts without editing or rerendering completed exam PDFs."""
from reportlab.pdfgen.canvas import Canvas


class ExamPages(Canvas):
    def __init__(self,*args,footer_font,**kwargs):
        super().__init__(*args,**kwargs)
        self._footer_font=footer_font
        self._page_states=[]

    def showPage(self):
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
