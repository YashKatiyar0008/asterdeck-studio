"""Asterdeck V3: extractive research mode and attributed editorial imagery."""
import re, io, base64, urllib.parse, urllib.request, concurrent.futures
from functools import lru_cache
from PIL import Image, ImageOps, ImageDraw, ImageFont
import engine

def topic_of(prompt):
    p=engine.clean(prompt,240)
    p=re.sub(r'^(?:please\s+)?(?:create|make|generate|design|prepare|build)\s+(?:me\s+)?(?:a\s+|an\s+)?(?:\d+[- ]slide\s+)?(?:pptx?|powerpoint(?: presentation)?|presentation|deck|slides?)\s*(?:on|about|for|of)?\s*','',p,flags=re.I)
    return p.strip(' .?!') or 'Presentation'

def sports(count):
    rows=[
        ('Why sports matter','Movement, connection and personal growth','sports athletes stadium',[('Physical health','Regular activity supports cardiovascular fitness, strength and coordination.'),('Mental wellbeing','Enjoyable physical activity can help manage stress and improve mood.'),('Social connection','Shared practice and competition create opportunities for friendship and belonging.')]),
        ('The world of sports','Different formats build different skills','football basketball tennis sports',[('Team sports','Football, basketball and volleyball require communication and coordinated decisions.'),('Individual sports','Tennis, swimming and athletics challenge personal technique and concentration.'),('Adventure and recreation','Cycling, climbing and recreational games offer varied ways to stay active.')]),
        ('Training for performance','Build skills progressively and recover well','athletics running training track',[('Warm up','Prepare for movement with an appropriate gradual warm-up.'),('Practice','Develop technique through consistent, age-appropriate practice.'),('Recover','Allow time for rest, hydration and recovery between sessions.')]),
        ('Teamwork and leadership','A strong team is more than individual talent','volleyball team sport players',[('Communication','Share information and listen to teammates during play.'),('Shared goals','Agree on roles, strategies and fair expectations.'),('Respect','Support teammates and opponents, including when results are disappointing.')]),
        ('Fair play and inclusion','Make participation safe and welcoming','inclusive sports wheelchair basketball',[('Fair competition','Follow the rules and respect officials and opponents.'),('Accessibility','Adapt equipment and formats so more people can participate.'),('Safety','Use appropriate facilities, equipment and supervision for the activity.')]),
        ('Sports and society','From community games to global events','sports stadium spectators',[('Community','Local clubs bring people together around shared interests.'),('Education','School sports complement classroom learning with practical cooperation.'),('Careers','Sports support roles in coaching, journalism, medicine and event management.')]),
        ('Technology in sport','Feedback helps athletes and teams learn','sports athletics timing equipment',[('Measurement','Timing and motion data can reveal patterns in performance.'),('Video review','Recorded play helps coaches explain tactics and technique.'),('Equipment','Design improvements can support comfort, accessibility and safety.')]),
        ('Getting involved','Choose an activity that suits your interests','community outdoor sports park',[('Explore','Try enjoyable activities in a supportive environment.'),('Find a group','Join a school club or community program that welcomes beginners.'),('Set a goal','Focus on learning and enjoyment rather than comparing yourself with others.')])
    ]
    return rows[:min(len(rows),count-2)]

@lru_cache(maxsize=64)
def encyclopedia(topic):
    p=urllib.parse.urlencode({'action':'query','generator':'search','gsrsearch':topic,'gsrlimit':6,'prop':'extracts|info','explaintext':1,'exchars':7500,'inprop':'url','format':'json','formatversion':2})
    d=engine.request_json('https://en.wikipedia.org/w/api.php?'+p,timeout=9)
    pages=sorted(d.get('query',{}).get('pages',[]),key=lambda x:x.get('index',999))
    return [x for x in pages if x.get('extract') and '(disambiguation)' not in x.get('title','')]

def sentences(t):
    t=re.sub(r'(?m)^=+.*?=+\s*$','',t)
    out=[]
    for s in re.split(r'(?<=[.!?])\s+|\n+',t):
        s=engine.clean(s,600)
        if 45<=len(s)<=420 and not re.match(r'^(See also|References|External links)',s,re.I):out.append(s)
    return out

def draft(d):
    prompt=engine.clean(d.get('prompt'),4000);topic=topic_of(prompt)
    count=max(3,min(20,int(d.get('count',8))))
    source=str(d.get('source') or '').strip()[:35000]
    rows=[];sources=[];warnings=[]
    is_sports=topic.lower() in ('sport','sports','sports and games','importance of sports','benefits of sports')
    if is_sports and not source:
        for title,sub,query,items in sports(count):rows.append((title,sub,query,[{'heading':h,'body':b} for h,b in items],[]))
        warnings.append('Sports content uses an original built-in educational outline; no invented statistics.')
    else:
        if source:
            chunks=sentences(source)
            for i in range(0,len(chunks),3):
                ss=chunks[i:i+3]
                if not ss:continue
                rows.append(('Document insight '+str(i//3+1),'From the supplied document',topic,[{'heading':'Point '+str(j+1),'body':engine.clean(v,205)} for j,v in enumerate(ss)],[]))
        else:
            try:pages=encyclopedia(topic)
            except Exception:pages=[];warnings.append('Wikipedia retrieval unavailable.')
            for p in pages:
                ss=sentences(p['extract'])
                if not ss:continue
                sid=len(sources)+1
                sources.append({'id':sid,'title':p['title'],'url':p.get('fullurl') or 'https://en.wikipedia.org/?curid='+str(p['pageid']),'excerpt':engine.clean(' '.join(ss[:5]),1000),'type':'Wikipedia extract (CC BY-SA; review original)'})
                for i in range(0,min(len(ss),9),3):
                    group=ss[i:i+3]
                    rows.append((p['title'] if i==0 else p['title']+' — continued','Research extract · review the source',p['title'],[{'heading':'Key fact '+str(j+1),'body':engine.clean(v,205)} for j,v in enumerate(group)],[sid]))
    if not rows:raise ValueError('No topic-specific material was found. Try a more specific topic, upload text, or configure Sarvam AI.')
    n=min(count-2,len(rows)); chosen=rows[:n]; total=n+2
    slides=[{'title':topic[:1].upper()+topic[1:],'subtitle':'An illustrated introduction','layout':'title','items':[],'notes':'Welcome. Today we explore '+topic+'.','image_query':topic}]
    for i,(title,sub,q,items,refs) in enumerate(chosen):
        slides.append({'title':title,'subtitle':sub,'layout':['split','comparison','process','cards','diagram','split'][(i)%6],'items':items,'notes':title+'. '+' '.join(x['heading']+'. '+x['body'] for x in items),'citations':refs,'image_query':q})
    recap=[{'heading':x[0],'body':x[3][0]['body']} for x in chosen[:3]]
    slides.append({'title':'Key takeaways','subtitle':'What to remember','layout':'closing','items':recap,'notes':'To conclude: '+' '.join(x['body'] for x in recap),'image_query':topic})
    if total<count:warnings.append('Only '+str(total)+' slides of non-repeated content were available; add source material for a longer deck.')
    if d.get('language','en-IN')!='en-IN':warnings.append('Research mode uses English; configure Sarvam for multilingual content.')
    return {'title':slides[0]['title'],'slides':slides,'sources':sources,'language':'en-IN','warnings':warnings,'generationMode':'Research draft' if not is_sports else 'Curated educational draft'}

def plain(s):
    return engine.clean(s,600)

STOP=set('a an the of in on to for and with from by is are how why what about introduction overview conclusion key takeaways new future role importance impact benefits presentation slide photo photograph image picture design example using use based'.split())
def terms(t):
    return {w.rstrip('s') for w in re.findall(r'[a-z0-9]{3,}',t.lower()) if w not in STOP}
def rank_image(p,query,topic):
    info=(p.get('imageinfo') or [{}])[0]; meta=info.get('extmetadata',{})
    title=p.get('title',''); description=plain((meta.get('ImageDescription') or {}).get('value',''))
    q=terms(query); t=terms(topic); n=terms(title); desc=terms(description)
    if not q:return -1
    hit=q & (n|desc); subject=t & (n|desc)
    if not hit or len(hit)/len(q)<.5 or (len(q)>1 and len(hit)<2):return -1
    if not (q & n):return -1
    if re.search(r'\b(null modem|serial adapter|connector|cable|unrelated)\b',title,re.I) and not re.search(r'modem|adapter|connector|cable',query,re.I):return -1
    if re.search(r'\b(logo|icon|flag|signature|coat of arms|poster|stamp|map|screenshot|diagram|chart|symbol)\b',title,re.I) and not re.search(r'logo|map|diagram|chart|flag|poster',query,re.I):return -1
    if info.get('mime') not in ('image/jpeg','image/png','image/webp'):return -1
    return 8*len(q&n)+3*len(q&desc)+2*len(subject)+2*len(hit)/len(q)

@lru_cache(maxsize=40)
def photo(query,topic=''):
    params=urllib.parse.urlencode({'action':'query','generator':'search','gsrsearch':query+' filetype:bitmap','gsrnamespace':6,'gsrlimit':15,'prop':'imageinfo','iiprop':'url|extmetadata|mime|size','iiurlwidth':700,'format':'json','formatversion':2})
    d=engine.request_json('https://commons.wikimedia.org/w/api.php?'+params,timeout=8)
    pages=d.get('query',{}).get('pages',[])
    candidates=sorted(((rank_image(p,query,topic),p) for p in pages),key=lambda x:x[0],reverse=True)
    for score,p in candidates[:4]:
        if score<0:break
        info=(p.get('imageinfo') or [{}])[0];meta=info.get('extmetadata',{})
        get=lambda k:plain((meta.get(k) or {}).get('value',''))
        license=get('LicenseShortName')
        if not re.match(r'^(CC BY(?:-SA)?(?:\s|$)|CC0|Public domain)',license,re.I):continue
        url=info.get('thumburl','') or info.get('url','')
        if urllib.parse.urlparse(url).hostname!='upload.wikimedia.org':continue
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'AsterdeckStudio/3.1 (educational presentation editor)'})
            with urllib.request.urlopen(req,timeout=5) as r: raw=r.read(3000001)
            if len(raw)>3000000:continue
            im=Image.open(io.BytesIO(raw))
            if im.width*im.height>25000000:continue
            im.thumbnail((850,850));im=ImageOps.exif_transpose(im).convert('RGB')
            if min(im.size)<160:continue
            im=ImageOps.fit(im,(640,460),method=Image.Resampling.LANCZOS)
            b=io.BytesIO();im.save(b,format='JPEG',quality=82,optimize=True)
            return {'src':'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode(),'title':p.get('title','').removeprefix('File:'),'author':get('Artist') or 'See original file','license':license,'url':'https://commons.wikimedia.org/wiki/'+urllib.parse.quote(p['title'].replace(' ','_')),'modified':'Cropped for slide layout','query':query,'relevance':round(score,2),'kind':'photo'}
        except Exception:continue
    return None


def visual_query(slide,topic):
    title=engine.clean(slide.get('title'),100)
    q=engine.clean(slide.get('image_query'),110)
    combined=(topic+' '+title).lower()
    # Technical ideas are better explained by actual conceptual diagrams.
    if re.search(r'\b(dbms|database|sql|relational|normalization)\b',combined):
        if re.search(r'normalization|normal form|redundancy',title,re.I):return 'database normalization relational tables',True
        if re.search(r'transaction|acid|concurren',title,re.I):return 'database transaction ACID properties',True
        if re.search(r'query|sql|relational',title,re.I):return 'relational database SQL tables',True
        if re.search(r'index|b.tree',title,re.I):return 'database index tree',True
        if re.search(r'design|entity|schema',title,re.I):return 'database entity relationship schema',True
        if re.search(r'history|milestone|ingres|system r',title,re.I):return 'history relational database systems',True
        return 'database management system architecture',True
    return q or engine.clean(topic+' '+title,110), bool(re.search(r'\b(schema|algorithm|architecture|workflow|equation|normalization|protocol|conceptual model)\b',title,re.I))

def font(size,bold=False):
    for name in (['DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if bold else ['DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']):
        try:return ImageFont.truetype(name,size)
        except OSError:pass
    try:return ImageFont.load_default(size=size)
    except TypeError:return ImageFont.load_default()

def diagram(slide,topic,query):
    """Original, labelled visual summary of the actual slide, not a stock photo."""
    im=Image.new('RGB',(800,600),'#132333');d=ImageDraw.Draw(im)
    ink='#eff7ff';muted='#b6cbdc';accent='#69dbc5';panel='#203b50';line='#4d7a90'
    f=font(29,True); small=font(20); mini=font(16); titlefont=font(36,True)
    def wrap(t,ft,width,maxlines=3):
        t=str(t or '').strip();lines=[];row=''
        for word in t.split():
            test=(row+' '+word).strip()
            if d.textlength(test,font=ft)>width and row:lines.append(row);row=word
            else:row=test
        if row:lines.append(row)
        if len(lines)>maxlines:lines=lines[:maxlines];lines[-1]=lines[-1].rstrip('.')+'…'
        return lines
    def label(x,y,t,ft,width,fill=ink,maxlines=2):
        for j,row in enumerate(wrap(t,ft,width,maxlines)):d.text((x,y+j*(ft.size+7 if hasattr(ft,'size') else 25)),row,font=ft,fill=fill)
    def box(x,y,w,h,t,body=''):
        d.rounded_rectangle((x,y,x+w,y+h),radius=18,fill=panel,outline=line,width=2)
        label(x+20,y+14,t,f,w-40,ink,2)
        if body:label(x+20,y+80,body,mini,w-40,muted,3)
    def arrow(a,b):
        d.line((a,b),fill=accent,width=5)
        import math
        angle=math.atan2(b[1]-a[1],b[0]-a[0])
        d.polygon([b,(b[0]-15*math.cos(angle-.55),b[1]-15*math.sin(angle-.55)),(b[0]-15*math.cos(angle+.55),b[1]-15*math.sin(angle+.55))],fill=accent)
    title=engine.clean(slide.get('title'),100);items=slide.get('items') or []
    d.rounded_rectangle((18,18,782,582),radius=22,outline='#355164',width=2)
    d.text((40,35),'VISUAL EXPLAINER',font=mini,fill=accent)
    label(40,70,title,titlefont,715,ink,2)
    db=bool(re.search(r'\b(dbms|database|sql|relational|normalization)\b',topic+' '+title,re.I))
    if db and re.search(r'normalization|normal form|redundancy',title,re.I):
        box(45,205,305,145,'Combined table','Repeated attributes')
        box(450,175,305,140,'Entity table','Primary key')
        box(450,365,305,140,'Related table','Foreign key')
        arrow((350,260),(450,245));arrow((350,285),(450,425))
    elif db and re.search(r'sql|relational|design|entity|schema',title,re.I) and not re.search(r'history|milestone',title,re.I):
        box(42,220,315,180,'Example: Students','student_id (PK) • name')
        box(443,220,315,180,'Example: Enrolments','student_id (FK) • course')
        arrow((357,305),(443,305));d.text((363,270),'1 : N',font=mini,fill=accent)
        label(45,460,'Illustrative relationship using primary and foreign keys.',small,705,muted,2)
    elif db and not items:
        box(220,160,360,92,'Applications');box(220,292,360,92,'DBMS');box(220,424,360,92,'Stored data');arrow((400,252),(400,292));arrow((400,384),(400,424))
    elif slide.get('layout')=='chart' and items and all(isinstance(x.get('value'),(int,float)) and x['value']>=0 for x in items):
        m=max([x['value'] for x in items]+[1])
        for j,it in enumerate(items[:3]):
            y=180+j*115;label(45,y,it.get('heading',''),small,700,ink,1)
            d.rounded_rectangle((45,y+39,45+max(4,int(565*it['value']/m)),y+65),radius=8,fill=accent)
            d.text((630,y+37),str(it['value']),font=mini,fill=ink)
        label(45,525,slide.get('subtitle',''),mini,705,muted,1)
    else:
        labels=[engine.clean(x.get('heading'),65) for x in items[:3] if x.get('heading')]
        if not labels:labels=[engine.clean(slide.get('subtitle') or topic,65)]
        labels=labels[:3];n=len(labels)
        is_flow=slide.get('layout') in ('process','timeline')
        if n==1:
            box(105,250,590,130,labels[0])
            d.ellipse((364,172,436,244),outline=accent,width=4)
            d.line((400,244,400,250),fill=accent,width=4)
        else:
            center=(400,220)
            if is_flow:
                for j,t in enumerate(labels):
                    x=40+j*(720//n);width=720//n-25
                    box(x,280,width,175,t)
                    if j<n-1:arrow((x+width,365),(x+720//n,365))
                label(45,485,'Sequence of the slide’s key steps',small,700,muted,1)
            else:
                d.ellipse((353,172,447,266),fill='#245664',outline=accent,width=3)
                d.text((378,199),'KEY',font=mini,fill=ink)
                for j,t in enumerate(labels):
                    x=40+j*(720//n);width=720//n-22
                    arrow((400,266),(x+width//2,340))
                    box(x,340,width,155,t)
    d.text((40,548),'Asterdeck • original conceptual illustration',font=mini,fill=muted)
    b=io.BytesIO();im.save(b,'JPEG',quality=85,optimize=True)
    return {'kind':'diagram','src':'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode(),'title':title,'author':'Asterdeck','license':'Original conceptual illustration','url':'','query':query,'modified':'Generated from slide concepts'}

def decorate(out,enabled=True):
    if not enabled:return out
    slides=out['slides'];topic=out['title'];indices=list(range(len(slides)))
    def find(i):
        sl=slides[i];query,concept=visual_query(sl,topic)
        if concept or sl.get('layout')=='chart':return None,query
        try:
            result=photo(query,topic)
            if result:return result,query
        except Exception:pass
        words=[w for w in re.findall(r'[A-Za-z0-9]+',query) if w.lower() not in STOP]
        if len(words)>3:
            try:
                result=photo(' '.join(words[:3]),topic)
                if result:return result,query
            except Exception:pass
        return None,query
    seen=set();photos=0;diagrams=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        jobs={pool.submit(find,i):i for i in indices}
        for job,i in jobs.items():
            try:result,query=job.result()
            except Exception:result=None;query=slides[i].get('title',topic)
            if result and result['url'] not in seen:
                seen.add(result['url']);slides[i]['visual']=result;photos+=1
            else:
                slides[i]['visual']=diagram(slides[i],topic,query);diagrams+=1
    out['visualCount']=photos+diagrams
    out['photoCount']=photos;out['diagramCount']=diagrams
    out['visualAttemptCount']=len(indices)
    if diagrams:out.setdefault('warnings',[]).append(str(diagrams)+' slides use original conceptual diagrams instead of unsuitable or unavailable photographs.')
    return out
