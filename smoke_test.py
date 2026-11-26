"""Opt-in, time-limited deployment smoke test. Never logs credentials or source text."""
import os, time, json, base64, io, urllib.request, urllib.error
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

def fixture():
    writer=PdfWriter()
    page=writer.add_blank_page(width=612,height=792)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 50 720 Td (Solar photovoltaic panels convert sunlight into electricity.) Tj 0 -20 Td (Inverters convert direct current into alternating current.) Tj 0 -20 Td (A battery can store surplus energy for later use.) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream)
    # Uncompressed metadata fixture tests the old 10 MB limit without large page content.
    padding=DecodedStreamObject();padding.set_data(b'0'*(11*1024*1024))
    writer._root_object[NameObject('/AsterdeckTestPadding')]=writer._add_object(padding)
    buf=io.BytesIO();writer.write(buf);return buf.getvalue()

def emit(stage,ok,**extra):
    print('ASTERDECK_SMOKE '+json.dumps({'stage':stage,'pass':ok,**extra}),flush=True)

def run(port):
    try: deadline=float(os.getenv('ASTERDECK_SMOKE_TEST_UNTIL','0'))
    except ValueError:return
    if time.time()>deadline:return
    try:
        fd=os.open('/tmp/asterdeck_smoke_once',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    except FileExistsError:return
    base='http://127.0.0.1:'+str(port)
    def call(path,data=None,timeout=120):
        req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json','X-Demo-Code':os.getenv('DEMO_ACCESS_CODE','')})
        try:
            with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)
        except urllib.error.HTTPError as err:
            try: msg=json.loads(err.read()).get('error','')
            except Exception:msg=''
            raise ValueError('HTTP '+str(err.code)+' '+str(msg)[:200])
    extracted=''
    try:
        time.sleep(2);health=call('/api/health',timeout=8)
        emit('health',bool(health.get('ok')),version=health.get('version'),sarvam_configured=bool(health.get('ai')))
        data=fixture();out=call('/api/extract',{'name':'synthetic-solar.pdf','data':'data:application/pdf;base64,'+base64.b64encode(data).decode()},35)
        extracted=out.get('text','')
        emit('pdf_extract',len(data)>10*1024*1024 and 'photovoltaic panels' in extracted and 'inverters' in extracted.lower(),bytes=len(data),characters=len(extracted))
    except Exception as e:emit('pdf_or_health',False,error=str(e)[:240])
    try:
        result=call('/api/generate',{'prompt':'How solar photovoltaic power works','count':8,'audience':'General','purpose':'Teaching lesson','language':'en-IN','source':extracted,'research':True,'visuals':True,'mode':'ai'},230)
        slides=result.get('slides',[]);combined=' '.join(str(s.get('title',''))+' '+str(s.get('items','')) for s in slides).lower()
        mode=result.get('generationMode','');sources=result.get('sources',[]);queries=result.get('researchQueries',[])
        emit('sarvam_deck',len(slides)==8 and mode.startswith('Sarvam') and any(x in combined for x in ('photovoltaic','solar','sunlight')),slides=len(slides),mode=mode,source_count=len(sources),query_count=len(queries))
        emit('external_research',bool(sources and queries),sources=len(sources),queries=len(queries))
        images=[x.get('visual') for x in slides if x.get('visual')]
        emit('slide_images',bool(slides) and len(images)==len(slides) and all(v.get('src','').startswith('data:image/jpeg;base64,') and v.get('license') for v in images),count=len(images),slide_count=len(slides),photos=result.get('photoCount',0),diagrams=result.get('diagramCount',0),attempted=result.get('visualAttemptCount',0),titles=[v.get('title','')[:120] for v in images])
    except Exception as e:emit('sarvam_deck',False,error=str(e)[:240])
