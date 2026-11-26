import time, threading, hmac, collections
import engine
import visual_engine
import base64, io, json, os, urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pypdf import PdfReader
from docx import Document
from PIL import Image
ROOT=Path(__file__).parent
MAX=44*1024*1024
DOCUMENT_MAX=30*1024*1024

def rgb(value):
    return RGBColor.from_string(value.lstrip('#').upper())

def make_pptx(deck):
    prs=Presentation(); prs.slide_width=Inches(13.333333); prs.slide_height=Inches(7.5)
    for slide in deck['slides'][:30]:
        s=prs.slides.add_slide(prs.slide_layouts[6]); s.background.fill.solid(); s.background.fill.fore_color.rgb=rgb(slide['bg'])
        for e in slide['elements'][:100]:
            x,y,w,h=[Inches(float(e[k])/96) for k in ('x','y','w','h')]
            if e['kind']=='image':
                raw=base64.b64decode(e['src'].split(',',1)[1]); img=Image.open(io.BytesIO(raw)); img.thumbnail((1800,1800)); img=img.convert('RGB'); out=io.BytesIO(); img.save(out,format='JPEG',quality=90); out.seek(0)
                scale=min(w/img.width,h/img.height); iw=int(img.width*scale); ih=int(img.height*scale)
                s.shapes.add_picture(out,int(x+(w-iw)/2),int(y+(h-ih)/2),width=iw,height=ih)
            elif e['kind']=='rect':
                sh=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if e.get('round') else MSO_SHAPE.RECTANGLE,x,y,w,h); sh.fill.solid(); sh.fill.fore_color.rgb=rgb(e['color']); sh.line.fill.background()
                if e.get('round'): sh.adjustments[0]=0.08
            elif e['kind']=='text':
                sh=s.shapes.add_textbox(x,y,w,h); tf=sh.text_frame; tf.clear(); tf.word_wrap=True; tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0; tf.vertical_anchor=MSO_ANCHOR.TOP
                for j,line in enumerate(str(e.get('text','')).split('\n')):
                    p=tf.paragraphs[0] if j==0 else tf.add_paragraph(); p.text=line; p.alignment=PP_ALIGN.CENTER if e.get('align')=='center' else PP_ALIGN.LEFT; p.space_before=Pt(0); p.space_after=Pt(0); p.line_spacing=1.12
                    for run in p.runs:
                        run.font.name='Aptos'; run.font.size=Pt(float(e['size'])*.75); run.font.bold=bool(e.get('bold')); run.font.color.rgb=rgb(e['color'])
        notes=str(slide.get('notes',''))
        lookup={x.get('id'):x for x in deck.get('sources',[]) if isinstance(x,dict)}
        refs=[lookup[i] for i in slide.get('citations',[]) if i in lookup]
        if refs:notes+='\n\nSources (review original):\n'+'\n'.join(str(r.get('title',''))+' — '+str(r.get('url','')) for r in refs)
        visual=slide.get('visual') or {}
        if visual.get('url'):notes+='\n\nImage: '+str(visual.get('title',''))+' — '+str(visual.get('author',''))+' — '+str(visual.get('license',''))+' — '+str(visual['url'])+' — cropped for layout.'
        if notes:s.notes_slide.notes_text_frame.text=notes[:8000]
        transition=slide.get('transition','none')
        if transition in ('fade','slide','zoom'):
            tr=OxmlElement('p:transition'); tr.set('spd','med'); tr.set('advClick','1')
            effect=OxmlElement('p:fade' if transition=='fade' else 'p:push' if transition=='slide' else 'p:zoom')
            if transition=='slide': effect.set('dir','l')
            if transition=='zoom': effect.set('dir','in')
            tr.append(effect); s._element.append(tr)
    b=io.BytesIO(); prs.save(b); return b.getvalue()

def extract(data):
    name=data['name'].lower(); raw=base64.b64decode(data['data'].split(',',1)[-1],validate=True)
    if len(raw)>DOCUMENT_MAX: raise ValueError('Maximum document size is 30 MB.')
    if name.endswith('.pdf'):
        reader=PdfReader(io.BytesIO(raw)); parts=[]; total=0
        for p in reader.pages[:120]:
            t=(p.extract_text() or '')[:12000]; parts.append(t); total+=len(t)
            if total>=50000:break
        result='\n'.join(parts)
    elif name.endswith('.docx'): result='\n'.join(p.text for p in Document(io.BytesIO(raw)).paragraphs)
    elif name.endswith(('.txt','.md','.csv')): result=raw.decode('utf-8',errors='replace')
    else: raise ValueError('Supported: PDF, DOCX, TXT, MD and CSV.')
    if not result.strip(): raise ValueError('No selectable text found. Scanned PDFs require OCR before upload.')
    return result[:50000]

RATE=collections.defaultdict(collections.deque)
LOCK=threading.Lock()
def allow_paid(ip):
    now=time.monotonic()
    with LOCK:
        q=RATE[ip]
        while q and now-q[0]>60:q.popleft()
        if len(q)>=8:return False
        q.append(now);return True

class Handler(BaseHTTPRequestHandler):
    def send(self,status,body,typ='application/json',extra=None):
        if isinstance(body,dict): body=json.dumps(body).encode()
        self.send_response(status); self.send_header('Content-Type',typ); self.send_header('Content-Length',str(len(body))); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Cache-Control','no-store')
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path=='/api/health': self.send(200,{'ok':True,'ai':bool(os.getenv('SARVAM_API_KEY')),'provider':'Sarvam','researchDraft':True,'version':'3.6','protected':bool(os.getenv('DEMO_ACCESS_CODE'))})
        elif self.path.split('?')[0] in ('/','/index.html'): self.send(200,(ROOT/'index.html').read_bytes(),'text/html; charset=utf-8')
        else: self.send(404,{'error':'Not found'})
    def do_POST(self):
        try:
            n=int(self.headers.get('Content-Length',0))
            if not 0<n<=MAX: return self.send(413,{'error':'Invalid or oversized request'})
            d=json.loads(self.rfile.read(n))
            if self.path in ('/api/generate','/api/tts','/api/coach','/api/research'):
                code=os.getenv('DEMO_ACCESS_CODE','')
                if code and not hmac.compare_digest(self.headers.get('X-Demo-Code','').encode(),code.encode()):return self.send(403,{'error':'Demo access code required. Set it in the workspace.'})
                if not allow_paid(self.client_address[0]):return self.send(429,{'error':'Too many requests. Try again in a minute.'})
            if self.path=='/api/export': self.send(200,make_pptx(d),'application/vnd.openxmlformats-officedocument.presentationml.presentation',{'Content-Disposition':'attachment; filename="asterdeck.pptx"'})
            elif self.path=='/api/extract': self.send(200,{'text':extract(d)})
            elif self.path=='/api/generate':
                if d.get('mode')=='ai' and not os.getenv('SARVAM_API_KEY'):raise ValueError('Sarvam API key is not configured on the server.')
                if d.get('mode')=='research' or not os.getenv('SARVAM_API_KEY'):
                    out=visual_engine.draft(d)
                else:
                    d['prompt']=visual_engine.topic_of(d.get('prompt',''))
                    out=engine.generate(d)
                self.send(200,visual_engine.decorate(out,d.get('visuals',True)))
            elif self.path=='/api/research': self.send(200,engine.research(engine.clean(d.get('query'),240)))
            elif self.path=='/api/tts': self.send(200,engine.tts(d))
            elif self.path=='/api/coach': self.send(200,engine.coach(d))
            else: self.send(404,{'error':'Not found'})
        except urllib.error.HTTPError as e: self.send(502,{'error':f'AI provider returned HTTP {e.code}. Check API configuration or use local mode.'})
        except (ValueError,KeyError,TypeError) as e: self.send(400,{'error':str(e)[:300]})
        except Exception as e: self.log_error('%s',type(e).__name__); self.send(500,{'error':'Request could not be completed. Check server logs.'})
if __name__=='__main__':
    port=int(os.getenv('PORT','8000'))
    server=ThreadingHTTPServer(('0.0.0.0',port),Handler)
    if os.getenv('ASTERDECK_SMOKE_TEST_UNTIL'):
        import smoke_test
        threading.Thread(target=smoke_test.run,args=(port,),daemon=True).start()
    server.serve_forever()
