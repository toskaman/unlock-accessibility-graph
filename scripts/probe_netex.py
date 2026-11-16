import sys, csv, re, collections, xml.etree.ElementTree as ET
NS={'n':'http://www.netex.org.uk/netex'}
root=ET.parse(sys.argv[1]).getroot()
status={r['id']:r for r in csv.DictReader(open(sys.argv[2],encoding='utf-8-sig'),delimiter=';')}
sps=root.findall('.//n:StopPlace',NS)
def txt(e,p):
    x=e.find(p,NS); return x.text if x is not None else None
lifts=[];quays=0;qa=collections.Counter();idf=0
for sp in sps:
    lon=float(txt(sp,'n:Centroid/n:Location/n:Longitude') or 0); lat=float(txt(sp,'n:Centroid/n:Location/n:Latitude') or 0)
    inidf = 1.4<lon<3.6 and 48.1<lat<49.25
    idf+=inidf
    qs=sp.findall('n:quays/n:Quay',NS); quays+=len(qs)
    qnames=[txt(q,'n:Name') for q in qs]
    for q in qs:
        lim=q.find('.//n:AccessibilityLimitation',NS)
        if lim is not None: qa[(txt(lim,'n:StepFreeAccess'),txt(lim,'n:LiftFreeAccess'))]+=1
        else: qa['none']+=1
    for le in sp.findall('.//n:LiftEquipment',NS):
        lifts.append(dict(id=le.get('id'),sp=sp.get('id'),name=txt(le,'n:Name'),desc=txt(le,'n:Description'),idf=inidf,qnames=qnames,spname=txt(sp,'n:Name')))
print('stopplaces',len(sps),'in IDF bbox',idf,'quays',quays)
print('quay StepFree/LiftFree',qa.most_common())
print('lifts',len(lifts),'IDF lifts',sum(l['idf'] for l in lifts))
ids={l['id'] for l in lifts}
print('status rows',len(status),'lift ids found in status',len(ids & set(status)),'status ids not in netex',len(set(status)-ids))
sp_uuid={sp.get('id').split(':')[3] for sp in sps}
print('status gareid in netex sp uuid', sum(1 for r in status.values() if r['gareid'] in sp_uuid),'/',len(status))
slash=sum(1 for l in lifts if l['desc'] and ' / ' in l['desc'])
print('lift desc with " / "',slash)
ends=collections.Counter(); qmatch=0
for l in lifts:
    if not l['desc'] or ' / ' not in l['desc']: continue
    for side in l['desc'].split(' / '):
        s=side.strip()
        if re.match(r'(?i)voies?\b',s): ends['<VOIE>']+=1
        else: ends[re.sub(r'\d+','#',s.lower())[:40]]+=1
print('endpoint kinds',ends.most_common(40))
import random; random.seed(1)
for l in random.sample([l for l in lifts if l['idf']],15): print(l['spname'],'|',l['name'],'|',l['desc'],'|',l['qnames'][:8])
