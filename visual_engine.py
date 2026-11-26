"""Asterdeck V3: extractive research mode and attributed editorial imagery."""
import re, io, base64, urllib.parse, urllib.request, concurrent.futures
from functools import lru_cache
from PIL import Image, ImageOps
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
    if not hit or len(hit)/len(q)<.34 or (len(q)>1 and not (q & n) and len(hit)<2):return -1
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
            return {'src':'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode(),'title':p.get('title','').removeprefix('File:'),'author':get('Artist') or 'See original file','license':license,'url':'https://commons.wikimedia.org/wiki/'+urllib.parse.quote(p['title'].replace(' ','_')),'modified':'Cropped for slide layout','query':query,'relevance':round(score,2)}
        except Exception:continue
    return None

def decorate(out,enabled=True):
    if not enabled:return out
    slides=out['slides'];topic=out['title']; indices=[i for i,s in enumerate(slides) if s.get('layout') not in ('chart','closing')][:10]
    if 0 not in indices:indices.insert(0,0)
    def find(i):
        sl=slides[i];query=engine.clean(sl.get('image_query') or (topic+' '+sl['title']),110)
        try:
            result=photo(query,topic)
            if result:return result
        except Exception:pass
        # Retry a narrower subject query rather than accept an unrelated generic photo.
        words=[w for w in re.findall(r'[A-Za-z0-9]+',query) if w.lower() not in STOP]
        if len(words)>2:
            try:
                result=photo(' '.join(words[:3]),topic)
                if result:return result
            except Exception:pass
        if i==0 and query.lower()!=topic.lower():
            try:return photo(topic,topic)
            except Exception:pass
        return None
    seen=set();found=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(find,i):i for i in indices}
        for f,i in jobs.items():
            try:
                result=f.result()
                if result and result['url'] not in seen:
                    seen.add(result['url']);slides[i]['visual']=result;found+=1
            except Exception:pass
    out['visualCount']=found
    out['visualAttemptCount']=len(indices)
    if found<len(indices):out.setdefault('warnings',[]).append('No sufficiently relevant licensed image was found for some slides; those use editable graphics instead.')
    return out
