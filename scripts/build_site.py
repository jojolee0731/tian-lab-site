#!/usr/bin/env python3
"""Build the static trilingual site. No network or third-party packages required."""
from pathlib import Path
from html import escape
import json
from urllib.parse import quote
import argparse

ROOT=Path(__file__).resolve().parents[1]
BASE='https://jojolee0731.github.io/tian-lab-site/'
LANGS=('en','zh','es')
PAGES=('index','research','publications','people','join','collaborate','news')
def tri(en,zh,es): return dict(zip(LANGS,(en,zh,es)))
def t(value,lang): return value.get(lang,value.get('en','')) if isinstance(value,dict) else str(value or '')
def e(value): return escape(str(value),quote=True)
def read(name): return json.loads((ROOT/'data'/name).read_text())
source=read('site.json')
UI={
'research':tri('Research','研究方向','Investigación'), 'publications':tri('Publications','研究成果','Publicaciones'), 'people':tri('People','团队成员','Equipo'), 'join':tri('Join','加入我们','Únete'), 'collaborate':tri('Collaborate','学术合作','Colaborar'), 'news':tri('News archive','新闻归档','Noticias'),
'index':tri('Brain barriers, molecular tools & imaging','脑屏障、分子工具与成像','Barreras cerebrales, herramientas moleculares e imagen'),
'skip':tri('Skip to content','跳至正文','Saltar al contenido'), 'menu':tri('Menu','导航菜单','Menú'), 'navigation':tri('Main navigation','主导航','Navegación principal'), 'languages':tri('Language','语言','Idioma'),
'explore':tri('Explore our research','了解研究方向','Explorar la investigación'), 'allpapers':tri('All publications','全部论文','Todas las publicaciones'), 'allpeople':tri('Meet the team','认识团队成员','Conoce al equipo'),
'paper':tri('Read paper','阅读论文','Leer el artículo'), 'evidence':tri('Evidence & context','证据与适用范围','Evidencia y contexto'), 'question':tri('The question','科学问题','La pregunta'), 'approach':tri('Our approach','研究思路','Nuestro enfoque'),
'outcome':tri('What this adds','科学贡献','Qué aporta'), 'recent':tri('Recent publications','最近发表','Publicaciones recientes'), 'stories':tri('Research in focus','代表性研究','Investigación destacada'),
'focus':tri('Research interests','研究兴趣','Intereses de investigación'), 'affiliation':tri('Affiliation','所在单位','Afiliación'), 'joined':tri('Joined','入组时间','Incorporación'), 'details':tri('Profile & contact','资料与联系','Perfil y contacto'),
'postdoc':tri('Postdoctoral researchers','博士后','Investigadores posdoctorales'), 'student':tri('Research students','研究生','Estudiantes de investigación'), 'staff':tri('Research support','科研支持','Apoyo a la investigación'), 'admin':tri('Lab administration','课题组行政联系','Administración del laboratorio'),
'year':tri('Year','年份','Año'), 'topic':tri('Research theme','研究主题','Tema de investigación'), 'all':tri('All','全部','Todas'), 'reset':tri('Reset filters','重置筛选','Restablecer filtros'), 'results':tri('publications shown','篇论文','publicaciones visibles'), 'noresults':tri('No matching publications. Try another filter.','没有符合条件的论文，请调整筛选。','No hay resultados. Prueba otro filtro.'),
'cover':tri('Journal cover illustration','期刊封面插画','Ilustración de portada'), 'covers':tri('Covers & visual stories','封面与视觉故事','Portadas e historias visuales'), 'issue':tri('View journal issue','查看期刊当期目录','Ver el número de la revista'), 'coverrecord':tri('View cover record','查看封面条目','Ver registro de portada'),
'contact':tri('Contact Xiaohe Tian','联系田肖和老师','Contactar con Xiaohe Tian'), 'location':tri('Chengdu, China','中国 · 成都','Chengdu, China'), 'featured':tri('Selected work','代表作','Trabajo destacado'),
'applications':tri('Applications & collaborations','拓展应用与合作','Aplicaciones y colaboraciones'),
}
HERO=tri('Understanding brain barriers. Designing molecular tools. Reading disease biology.','理解脑屏障，设计分子工具，读出疾病变化。','Comprender las barreras cerebrales. Diseñar herramientas moleculares. Observar la biología de la enfermedad.')
INTRO=tri('We study how brain barriers recognize and transport molecular cargo, and how these processes change in disease. We combine multivalent interface design, molecular probes, and imaging across scales to investigate barrier function, pathological molecule clearance, and responses to intervention.','我们研究分子如何被脑屏障识别与运输，以及这些过程如何影响脑疾病。通过多价界面设计、分子探针和跨尺度成像，我们探索屏障功能、病理分子清除与干预响应之间的联系。','Estudiamos cómo las barreras cerebrales reconocen y transportan moléculas y cómo estos procesos cambian en la enfermedad. Combinamos el diseño de interfaces multivalentes, sondas moleculares e imagen a distintas escalas para investigar la función de las barreras, la eliminación de moléculas patológicas y la respuesta a intervenciones.')
THEMES=[
{'id':'barriers','title':tri('Recognition & transport at brain barriers','脑屏障的识别与运输','Reconocimiento y transporte en barreras cerebrales'),'short':tri('How do molecular interfaces influence receptor recognition, sorting, and transport?','分子界面如何影响受体识别、分选与跨屏障运输？','¿Cómo influyen las interfaces moleculares en el reconocimiento, la clasificación y el transporte?'),'approach':tri('We investigate multivalent interactions and receptor-mediated transport, including LRP1, at the blood–brain and blood–brain tumor barriers (BBB/BBTB). Molecular design is connected to transport behavior, rather than treated as an end in itself.','围绕血脑屏障和血脑肿瘤屏障（BBB/BBTB），研究多价相互作用及 LRP1 等受体介导的运输，将分子界面设计与识别、分选和转运行为联系起来。','Investigamos interacciones multivalentes y transporte mediado por receptores, incluido LRP1, en las barreras hematoencefálica y hematotumoral cerebral. Relacionamos el diseño molecular con el comportamiento del transporte.'),'papers':['sttt-2025-multivalent-clearance','sciadv-2020-precision','sciadv-2020-shuttling','srep-2015-lrp1']},
{'id':'imaging','title':tri('Molecular tools to read biological change','读出生物变化的分子工具','Herramientas para observar cambios biológicos'),'short':tri('What can a molecular probe reveal about a cell state that an image alone cannot?','分子探针能让哪些细胞状态和微环境变化变得可测量？','¿Qué puede revelar una sonda molecular sobre el estado de una célula?'),'approach':tri('Probe chemistry, fluorescence lifetime measurements, super-resolution microscopy, and multimodal imaging connect molecular interactions with cellular and tissue-level readouts. Each method is chosen for the biological question and the scale of evidence it can support.','通过探针化学、荧光寿命、超分辨显微与多模态成像，将分子相互作用连接到细胞和组织层面的读出，根据科学问题选择方法与证据尺度。','La química de sondas, las medidas de vida media de fluorescencia, la microscopía de superresolución y la imagen multimodal conectan interacciones moleculares con lecturas celulares y tisulares. Elegimos cada método según la pregunta y el alcance de su evidencia.'),'papers':['acs-2026-lipid-droplets','bios-2026-telomere','csr-2025-metal-complexes','jmcb-2025-flim']},
{'id':'clearance','title':tri('Clearance pathways & disease response','清除通路与疾病响应','Vías de eliminación y respuesta en la enfermedad'),'short':tri('How are barrier function, pathological molecule clearance, and disease-associated cell states connected?','屏障功能、病理分子清除与疾病相关细胞状态如何相互关联？','¿Cómo se relacionan la función de las barreras, la eliminación de moléculas patológicas y los estados celulares?'),'approach':tri('Alzheimer’s disease provides a shared context for work on amyloid-β clearance, microglial lipid droplets, and the choroid plexus–cerebrospinal fluid pathway. Imaging and intervention studies are interpreted within their specific experimental or clinical setting.','以阿尔茨海默病为重要研究背景，关注 Aβ 清除、小胶质细胞脂滴以及脉络丛—脑脊液通路。成像与干预研究均在各自的实验或临床条件下解释。','La enfermedad de Alzheimer conecta el estudio de la eliminación de amiloide-β, las gotas lipídicas de la microglía y la vía plexo coroideo–líquido cefalorraquídeo. Interpretamos los estudios de imagen e intervención dentro de su contexto experimental o clínico.'),'papers':['alz-2026-choroid-plexus','sttt-2025-multivalent-clearance','acs-2026-lipid-droplets','alz-2026-dclva']}
]
STORIES=[
{'id':'transport-clearance','theme':'barriers','paper':'sttt-2025-multivalent-clearance','title':tri('From molecular recognition to amyloid-β clearance','从分子识别走向 Aβ 清除','Del reconocimiento molecular a la eliminación de amiloide-β'),'question':tri('Can changing a multivalent interface alter how the brain barrier handles amyloid-β?','改变多价分子界面，能否影响脑屏障对 Aβ 的运输与清除？','¿Puede una interfaz multivalente modificar el transporte y la eliminación de amiloide-β?'),'outcome':tri('A transport-focused line of research connects receptor recognition and molecular design with pathological molecule clearance. The 2025 study reports enhanced Aβ clearance and cognitive outcomes in an APP/PS1 mouse model.','这一研究主线把受体识别和分子设计连接到病理分子清除。2025 年研究在 APP/PS1 小鼠模型中报告了 Aβ 清除增强及认知相关改善。','Esta línea relaciona reconocimiento por receptores y diseño molecular con eliminación de moléculas patológicas. El estudio de 2025 informa de mejoras en la eliminación de Aβ y resultados cognitivos en un modelo murino APP/PS1.'),'limit':tri('Preclinical mouse evidence; it does not establish efficacy in patients.','证据来自临床前小鼠研究，不等同于患者疗效。','Evidencia preclínica en ratones; no demuestra eficacia en pacientes.'),'image':'./assets/images/sttt-2025-november-cover.jpg','caption':UI['cover']},
{'id':'microglial-state','theme':'imaging','paper':'acs-2026-lipid-droplets','title':tri('Reading lipid-droplet states in microglia','读出小胶质细胞脂滴状态','Observar estados de gotas lipídicas en microglía'),'question':tri('How do different Aβ25–35 assemblies relate to lipid-droplet remodeling and microglial function?','不同 Aβ25–35 组装态与脂滴重塑和小胶质细胞功能有何联系？','¿Cómo se relacionan distintos ensamblajes de Aβ25–35 con las gotas lipídicas y la función microglial?'),'outcome':tri('The polarity-sensitive probe BODIPY-LD reads lipid-droplet burden and microenvironment changes from cells to APP/PS1 brain tissue, linking lipid accumulation with reduced phagocytosis in BV2 cellular experiments.','极性敏感探针 BODIPY-LD 将脂滴负荷与微环境变化转为成像读出，从细胞延伸至 APP/PS1 脑组织，并在 BV2 细胞实验中将脂滴积累与吞噬能力下降联系起来。','La sonda BODIPY-LD, sensible a la polaridad, permite observar carga lipídica y cambios del microambiente en células y tejido cerebral APP/PS1, relacionando la acumulación lipídica con una fagocitosis reducida en experimentos con células BV2.'),'limit':tri('Cellular and mouse-tissue evidence; these readouts are not a validated clinical diagnostic test.','证据来自细胞及小鼠脑组织研究，尚不能据此认定为临床诊断方法。','Evidencia celular y de tejido murino; estas lecturas no constituyen una prueba diagnóstica clínica validada.'),'image':'./assets/images/news/2026-acs-sensors-bodipy-ld-toc.png','caption':tri('Paper graphical abstract · ACS Sensors, 2026','论文图文摘要 · ACS Sensors，2026','Resumen gráfico del artículo · ACS Sensors, 2026')},
{'id':'csf-clearance','theme':'clearance','paper':'alz-2026-choroid-plexus','title':tri('A barrier-and-clearance perspective on Alzheimer’s disease','从屏障与清除通路理解阿尔茨海默病','Alzheimer desde las barreras y las vías de eliminación'),'question':tri('How is choroid plexus remodeling linked to CSF-mediated clearance and disease progression?','脉络丛重塑与脑脊液介导的清除及疾病进展有何关联？','¿Cómo se relaciona la remodelación del plexo coroideo con la eliminación mediada por LCR y la progresión de la enfermedad?'),'outcome':tri('This study connects choroid plexus remodeling with impaired CSF-mediated clearance, adding a complementary perspective to blood–brain barrier transport research.','该研究将脉络丛重塑与脑脊液介导的清除受损相联系，为血脑屏障运输研究补充另一条屏障与清除通路视角。','El estudio vincula la remodelación del plexo coroideo con una eliminación mediada por LCR alterada, aportando una perspectiva complementaria al transporte por la barrera hematoencefálica.'),'limit':tri('A reported association does not by itself establish causality or treatment benefit.','研究报告的关联不应直接解释为因果关系或治疗获益。','La asociación observada no demuestra por sí sola causalidad ni beneficio terapéutico.'),'image':'./assets/images/news/2026-adj-choroid-plexus-csf-clearance-dispatch.png','caption':tri('Research illustration · not experimental data','研究主题示意图 · 非实验数据','Ilustración de investigación · no son datos experimentales')}
]

class Site:
 def __init__(self,lang):
  self.lang=lang;self.prefix='./' if lang=='en' else '../'
  self.pubs=read('publications.json');self.people=read('people.json');self.contact=read('contact.json')
  self.pmap={p['id']:p for p in self.pubs['items']}
 def tx(self,x): return e(t(x,self.lang))
 def u(self,k):return self.tx(UI[k])
 def asset(self,path):return self.prefix+path.removeprefix('./')
 def img(self,path,alt,cls='',eager=False):
  return f'<img src="{e(self.asset(path))}" alt="{self.tx(alt)}" class="{cls}" width="800" height="800" loading="{"eager" if eager else "lazy"}" decoding="async">'
 def link(self,page,label,cls='text-link',anchor=''):
  return f'<a class="{cls}" href="{page}.html{anchor}">{label}<span aria-hidden="true"> ↗</span></a>'
 def email(self,subject=None,cls='button'):
  address=self.contact['pi']['email'];url='mailto:'+address+ ('?subject='+quote(subject) if subject else '')
  return f'<a class="{cls}" href="{e(url)}">{self.u("contact")} <span aria-hidden="true">↗</span></a>'
 def paperlink(self,pid):
  p=self.pmap[pid];return self.link('publications',e(p['journal'])+' · '+e(p['year']),'text-link','#paper-'+pid)
 def heading(self,title,body='',kicker='',level=1):
  return f'<div class="section-heading">'+(f'<p class="eyebrow">{kicker}</p>' if kicker else '')+f'<h{level}>{title}</h{level}>'+ (f'<p class="lede">{body}</p>' if body else '')+'</div>'
 def theme_cards(self):
  return '<div class="theme-grid">'+''.join(f'<a class="theme-card" href="research.html#{v["id"]}"><span class="index">0{i+1}</span><h3>{self.tx(v["title"])}</h3><p>{self.tx(v["short"])}</p><span class="arrow" aria-hidden="true">↗</span></a>' for i,v in enumerate(THEMES))+'</div>'
 def story(self,v,full=False):
  parts=f'<p class="eyebrow">{self.tx(next(x["title"] for x in THEMES if x["id"]==v["theme"]))}</p><h3>{self.tx(v["title"])}</h3>'
  if full:parts+=f'<h4>{self.u("question")}</h4><p>{self.tx(v["question"])}</p>'
  parts+=f'<p>{self.tx(v["outcome"])}</p><p class="evidence"><strong>{self.u("evidence")}:</strong> {self.tx(v["limit"])}</p>{self.paperlink(v["paper"])}'
  if not full:parts+=self.link('research',self.tx(tri('Research story','研究解读','Historia de investigación')),'quiet-link','#'+v['id'])
  return f'<article class="story {"story-full" if full else ""}" id="{v["id"]}"><figure>{self.img(v["image"],v["caption"])}<figcaption>{self.tx(v["caption"])}</figcaption></figure><div class="story-copy">{parts}</div></article>'
 def paper(self,p,compact=False):
  doi=p.get('doi',''); url=p.get('url') or 'https://doi.org/'+doi
  topics=' '.join(p['topics']); journal=e(p['journal'])+' · '+e(p['year'])
  if not compact:
   if p.get('volume'): journal+=' · '+e(p['volume'])+(':'+e(p['pages']) if p.get('pages') else '')
   kind={'research':tri('Research article','原创研究','Artículo de investigación'),'review':tri('Review','综述','Revisión'),'clinical':tri('Clinical study','临床研究','Estudio clínico')}
   journal+='<span class="paper-kind">'+self.tx(kind[p['type']])+('</span><span class="selected-label">'+self.u('featured') if p['selected'] else '')+'</span>'
  details=''
  if not compact:
   authors=p['authors'];authors='; '.join(authors) if isinstance(authors,list) else authors
   details=f'<p class="authors">{e(authors)}</p><p>{self.tx(p.get("summary",{}))}</p><p class="paper-links"><a href="{e(url)}">{self.u("paper")} ↗</a>'+ (f'<span class="doi">DOI: {e(doi)}</span>' if doi else '')+'</p>'
  else:details=self.link('publications',self.u('paper'),'text-link','#paper-'+p['id'])
  return f'<article class="paper-row" id="paper-{p["id"]}" data-year="{p["year"]}" data-topics="{e(topics)}"><div class="paper-meta">{journal}</div><div><h3 lang="en">{e(p["title"])}</h3>{details}</div></article>'
 def member(self,p,mini=False):
  name=p['name'] if self.lang=='zh' else p.get('nameEn',p['name'])
  s=self.img(p['image'],name)+f'<div><h3>{e(name)}</h3><p class="member-role">{self.tx(p["role"])}</p>'
  if not mini:
   if t(p.get('focus'),self.lang):s+=f'<p class="member-focus">{self.tx(p["focus"])}</p>'
   s+='<details><summary>'+self.u('details')+'</summary><div class="member-details">'
   s+=f'<p>{self.tx(p["affiliation"])}</p><p>{self.u("joined")}: {e(p["joined"])}</p>'
   if p.get('email'):s+=f'<a href="mailto:{e(p["email"])}">{e(p["email"])}</a>'
   s+='</div></details>'
  else:s+=self.link('people',self.tx(tri('View profile','查看资料','Ver perfil')),'quiet-link','#person-'+p['id'])
  return f'<article class="member {"member-mini" if mini else ""}"'+('' if mini else f' id="person-{p["id"]}"')+'>'+s+'</div></article>'
 def actions(self):
  a=tri('A question worth exploring together.','从一个值得共同研究的问题开始。','Una pregunta para explorar juntos.')
  return '<section class="section action-band">'+self.heading(self.tx(a),'','',2)+'<div class="action-links">'+self.link('join',self.u('join'),'button')+self.link('collaborate',self.u('collaborate'),'button button-outline')+'</div></section>'
 def index(self):
  h='<section class="hero"><div class="hero-copy"><p class="eyebrow">'+self.tx(source['copy']['heroEyebrow'])+'</p><h1>'+(''.join('<span>'+e(v)+'</span>' for v in ['理解脑屏障，','设计分子工具，','读出疾病变化。']) if self.lang=='zh' else self.tx(HERO))+'</h1><p class="hero-body">'+self.tx(INTRO)+'</p><div class="hero-actions">'+self.link('research',self.u('explore'),'button')+self.link('join',self.u('join'),'button button-outline')+'</div></div><figure class="hero-art">'+self.img(STORIES[0]['image'],STORIES[0]['caption'],eager=True)+'<figcaption>'+self.u('cover')+' · STTT 2025<br>'+self.paperlink(STORIES[0]['paper'])+'</figcaption></figure></section>'
  h+='<section class="section" id="research">'+self.heading(self.tx(tri('Three connected questions.','三个相互连接的研究问题。','Tres preguntas conectadas.')),self.tx(tri('Molecular recognition shapes transport. Probes make its consequences measurable. Disease models reveal why it matters.','分子识别影响运输，探针使变化可测量，疾病研究揭示其生物学意义。','El reconocimiento molecular influye en el transporte. Las sondas permiten medir sus efectos. Los modelos de enfermedad revelan su relevancia.')),self.u('research'),2)+self.theme_cards()+'</section>'
  h+='<section class="section tinted" id="selected-work">'+self.heading(self.u('stories'),'','',2)+'<div class="story-grid">'+''.join(self.story(s) for s in STORIES)+'</div></section>'
  h+='<section class="section" id="publications"><div class="section-top">'+self.heading(self.u('recent'),'','',2)+self.link('publications',self.u('allpapers'))+'</div>'+''.join(self.paper(self.pmap[x],True) for x in self.pubs['recentIds'][:6])+'</section>'
  h+='<section class="section compact-section" id="news"><div class="section-top">'+self.heading(self.tx(tri('From the lab','研究动态','Actualidad del laboratorio')),'','',2)+self.link('news',self.u('news'))+'</div><div class="news-short">'
  for i,n in enumerate(source['news'][:3]): h+=f'<article><span class="date">{e(n["date"])}</span><h3><a href="news.html#news-{i+1}">{self.tx([tri("Choroid plexus remodeling and CSF-mediated clearance","脉络丛重塑与脑脊液介导的清除","Plexo coroideo y eliminación mediada por LCR"),tri("BODIPY-LD reveals microglial lipid-droplet states","BODIPY-LD 读出小胶质细胞脂滴状态","BODIPY-LD revela estados lipídicos en microglía"),tri("LD-TTP connects lipid droplets, LRP1, and Aβ uptake","LD-TTP 连接脂滴、LRP1 与 Aβ 摄取","LD-TTP conecta gotas lipídicas, LRP1 y captación de Aβ")][i])}</a></h3></article>'
  h+='</div></section>'
  h+='<section class="section tinted" id="people"><div class="section-top">'+self.heading(self.tx(tri('A team across disciplines.','一支跨学科的研究团队。','Un equipo entre disciplinas.')),self.tx(tri('Meet the people working across molecular design, imaging, and brain disease research.','认识参与分子设计、成像与脑疾病研究的团队成员。','Conoce a las personas que trabajan en diseño molecular, imagen y enfermedades cerebrales.')),self.u('people'),2)+self.link('people',self.u('allpeople'))+'</div><div class="people-preview">'
  ids=['member-15','member-01','member-07']
  chosen=[next((p for p in self.people['items'] if p['id']==i),self.people['items'][j]) for j,i in enumerate(ids)]
  pi=self.people['pi']; mini_pi={'id':'pi','name':'田肖和','nameEn':'Xiaohe Tian','role':tri('Principal investigator','课题组负责人','Investigador principal'),'image':pi['image']}
  h+=self.member(mini_pi,True).replace('#person-pi','#pi')+''.join(self.member(p,True) for p in chosen)+'</div></section>'+self.actions()
  return h
 def research(self):
  h='<section class="section page-intro">'+self.heading(self.u('research'),self.tx(INTRO),self.tx(tri('From interfaces to disease biology','从分子界面到疾病生物学','De interfaces a biología de la enfermedad')))+self.theme_cards()+'</section>'
  for i,v in enumerate(THEMES):
   h+=f'<section class="section theme-detail" id="{v["id"]}"><div><span class="index">0{i+1}</span><h2>{self.tx(v["title"])}</h2></div><div><h3>{self.u("question")}</h3><p class="lede">{self.tx(v["short"])}</p><h3>{self.u("approach")}</h3><p>{self.tx(v["approach"])}</p><div class="related-papers">'+''.join(self.paperlink(x) for x in v['papers'])+'</div></div></section>'
  h+='<section class="section tinted">'+self.heading(self.u('stories'),'','',2)+''.join(self.story(s,True) for s in STORIES)+'</section>'
  h+='<section class="section">'+self.heading(self.u('applications'),self.tx(tri('Related work extends molecular probes and intervention readouts to other biological settings, including liver and skin models, vaccine adjuvants, and cellular injury. These applications remain connected to specific publications rather than presented as separate core research programmes.','相关研究将分子探针与干预读出拓展到肝脏和皮肤模型、疫苗佐剂及细胞损伤等场景。这些应用通过具体论文呈现，作为主线之外的拓展与合作。','Otros trabajos extienden sondas y lecturas de intervención a modelos hepáticos y cutáneos, adyuvantes de vacunas y lesión celular. Estas aplicaciones se presentan mediante sus publicaciones como extensiones y colaboraciones.')),'',2)+self.link('publications',self.u('allpapers'))+'</section>'+self.actions()
  return h
 def publications(self):
  description=tri('A curated record of the lab’s published work. Follow a scientific question, or browse by year.','沿着科学问题阅读代表作，也可以按年份浏览已发表研究。','Una selección del trabajo publicado. Sigue una pregunta científica o explora por año.')
  h='<section class="section page-intro">'+self.heading(self.u('publications'),self.tx(description))+ '<div class="filters" hidden><label>'+self.u('year')+'<select id="filter-year"><option value="all">'+self.u('all')+'</option>'
  for y in sorted(set(x['year'] for x in self.pubs['items']),reverse=True):h+=f'<option value="{y}">{y}</option>'
  h+='</select></label><label>'+self.u('topic')+'<select id="filter-topic"><option value="all">'+self.u('all')+'</option>'
  for v in THEMES:h+=f'<option value="{v["id"]}">{self.tx(v["title"])}</option>'
  h+='<option value="applications">'+self.u('applications')+'</option></select></label><button type="button" id="reset-filters">'+self.u('reset')+'</button><p id="filter-count" role="status" data-label="'+self.u('results')+'"></p></div><p id="no-results" hidden>'+self.u('noresults')+'</p><div id="publication-list">'
  h+=''.join(self.paper(p) for p in sorted(self.pubs['items'],key=lambda p:(p['year'],p.get('publishedOnline','')),reverse=True))+'</div></section>'
  h+='<section class="section tinted" id="covers">'+self.heading(self.u('covers'),self.tx(tri('Visual interpretations of published research. Cover art is distinct from experimental evidence.','以视觉语言表达研究主题。封面插画与实验结果具有不同用途。','Interpretaciones visuales de la investigación publicada. Las portadas se distinguen de la evidencia experimental.')),'',2)+'<div class="cover-grid">'
  for c in source['covers']:
   label=self.u('coverrecord') if '202070296' in c['url'] else self.u('issue') if c['linkType']=='issue' else self.u('paper')
   h+='<figure>'+self.img(c['image'],c['alt'])+f'<figcaption><strong>{e(c["journal"])}</strong><span>{e(c["year"])}</span><p>{self.tx(c["title"])}</p><a href="{e(c["url"])}">{label} ↗</a>'
   if '202070296' in c['url']:h+='<br><a href="https://doi.org/10.1002/adma.202003901">'+self.u('paper')+' ↗</a>'
   h+='</figcaption></figure>'
  return h+'</div></section>'
 def people_page(self):
  pi=self.people['pi'];h='<section class="section page-intro">'+self.heading(self.u('people'),self.tx(tri('Researchers from different disciplines working together on brain barriers, molecular tools, and disease imaging.','不同学科背景的研究者，共同推进脑屏障、分子工具与疾病成像研究。','Investigadores de distintas disciplinas que trabajan juntos en barreras cerebrales, herramientas moleculares e imagen de la enfermedad.')))
  h+='<article class="pi-card" id="pi">'+self.img(pi['image'],pi.get('imageAlt',pi['name']))+'<div><p class="eyebrow">'+self.tx(tri('Principal investigator','课题组负责人','Investigador principal'))+'</p><h2>'+self.tx(tri('Xiaohe Tian, PhD','田肖和 博士','Xiaohe Tian, PhD'))+'</h2><p>'+self.tx(pi['role'])+'</p><p>'+self.tx(pi['bio'])+'</p><div class="link-list">'+''.join(f'<a href="{e(l["url"])}">{self.tx(l["label"])} ↗</a>' for l in pi['links'])+'</div><dl class="pi-facts">'+''.join('<div><dt>'+self.tx(f['label'])+'</dt><dd>'+self.tx(f['value'])+'</dd></div>' for f in pi.get('facts',[])[:2])+'</dl><details class="pi-credentials"><summary>'+self.tx(tri('Appointments & recognition','任职与人才计划','Cargos y reconocimientos'))+'</summary><p>'+self.tx(pi['facts'][2]['value'])+'</p></details>'+self.email()+'</div></article>'
  h+='<nav class="section-nav" aria-label="'+self.tx(tri('Team groups','成员分类','Grupos del equipo'))+'">'+''.join(f'<a href="#{g}">{self.u(g)} <span>{sum(p["group"]==g for p in self.people["items"])}</span></a>' for g in ('postdoc','student','staff','admin'))+'</nav></section>'
  for g in ('postdoc','student','staff'):
   h+=f'<section class="section people-section" id="{g}"><h2>{self.u(g)}</h2><div class="people-grid">'+''.join(self.member(p) for p in self.people['items'] if p['group']==g)+'</div></section>'
  admin=self.contact.get('admin')
  if admin:
   h+=f'<section class="section admin-card" id="admin">{self.img(admin["image"],admin["name"])}<div id="person-{admin["memberId"]}"><p class="eyebrow">'+self.u('admin')+'</p><h2>'+self.tx(admin['name'])+'</h2><p>'+self.tx(admin['role'])+'</p><p>'+self.tx(admin['responsibilities'])+f'</p><a href="mailto:{e(admin["email"])}">{e(admin["email"])}</a></div></section>'
  h+='<section class="section culture"><div>'+self.heading(self.tx(tri('Beyond the bench','科研之外','Más allá del laboratorio')),self.tx(tri('Music is part of Xiaohe Tian’s life outside research. The lab’s original “Nanoneuroscience in Rhythm” identity lives here, alongside the people behind the science.','音乐也是田肖和老师科研之外的生活组成部分。网站原有的“脑科学，有点节奏”留在这里，为严谨的研究介绍补充一点人的温度。','La música forma parte de la vida de Xiaohe Tian fuera de la investigación. La identidad original «Nanoneurociencia con ritmo» se conserva aquí, junto a las personas detrás de la ciencia.')),'',2)+'</div><figure>'+self.img('./assets/images/xiaohe-tian-drummer-hero.jpg',tri('Xiaohe Tian playing drums','田肖和演奏架子鼓','Xiaohe Tian tocando la batería'))+'</figure></section>'+self.actions()
  return h
 def join(self):
  h='<section class="section page-intro narrow">'+self.heading(self.tx(tri('Bring a question. Find a research fit.','带着问题，寻找适合自己的研究方向。','Trae una pregunta. Encuentra afinidad científica.')),self.tx(tri('Start with our research themes and publications, then tell us which question interests you and how your background connects to it.','先了解研究方向与论文，再告诉我们：你对哪个问题感兴趣，已有经历与它有什么联系。','Conoce nuestras líneas y publicaciones; después cuéntanos qué pregunta te interesa y cómo se relaciona con tu experiencia.')),self.u('join'))+'</section><section class="section join-grid"><div>'
  h+='<h2>'+self.tx(tri('Ways to enquire','可以咨询的方向','Motivos de consulta'))+'</h2>'
  entries=[tri('Graduate study: describe your intended degree, relevant preparation, and research interests.','研究生学习：说明拟申请学位、已有研究准备和感兴趣的问题。','Estudios de posgrado: indica el título al que aspiras, tu preparación e intereses.'),tri('Postdoctoral research: outline a scientific question and how your experience could contribute.','博士后研究：围绕具体科学问题，介绍已有工作和可能的贡献。','Investigación posdoctoral: plantea una pregunta y cómo podría contribuir tu experiencia.'),tri('Research visits or student projects: explain your current affiliation, scope, and proposed dates.','科研访问或学生项目：说明当前单位、计划内容与拟参与时间。','Visitas o proyectos estudiantiles: explica tu institución, el alcance y las fechas propuestas.')]
  h+='<ul class="prose-list">'+''.join('<li>'+self.tx(x)+'</li>' for x in entries)+'</ul><p class="note">'+self.tx(tri('These are enquiry routes, not a list of confirmed vacancies. Availability, eligibility, and admissions procedures must be confirmed for the relevant programme.','以上是咨询类别，不代表当前均有空缺。具体名额、资格与录取程序，以对应项目及官方招生通知为准。','Son vías de consulta, no una lista de vacantes confirmadas. La disponibilidad, los requisitos y la admisión dependen del programa correspondiente.'))+'</p>'+self.link('research',self.u('explore'))+'</div><div class="callout"><h2>'+self.tx(tri('A useful first email','第一封邮件可以包含','Qué incluir en el primer correo'))+'</h2><ol class="prose-list">'
  for x in [tri('A short CV and current affiliation.','简历与当前学习或工作单位。','Un CV breve y tu institución actual.'),tri('One or two representative outputs, with your own contribution explained.','1–2 项代表性工作，并说明自己的具体贡献。','Uno o dos trabajos representativos y tu contribución.'),tri('A research question linked to a lab theme or paper.','与课题组方向或论文相关的具体研究兴趣。','Una pregunta vinculada a una línea o publicación.'),tri('The type of opportunity and your proposed start date.','希望咨询的类别与计划开始时间。','El tipo de oportunidad y la fecha de inicio prevista.')]:h+='<li>'+self.tx(x)+'</li>'
  h+='</ol>'+self.email('Tian Lab — research enquiry')+'</div></section><section class="section narrow"><h2>'+self.tx(tri('Before applying','正式申请前','Antes de solicitar'))+'</h2><p>'+self.tx(tri('Discuss project fit, supervision arrangements, and practical requirements directly with the PI. Formal applications follow the university or hospital process.','请与 PI 沟通研究匹配度、指导安排及实际要求。正式申请仍需遵循大学或医院的相关流程。','Consulta con el investigador principal la afinidad del proyecto, la supervisión y los requisitos prácticos. Las solicitudes formales siguen el procedimiento universitario u hospitalario.'))+'</p><div class="link-list"><a href="https://yjs.cd120.com/">'+self.tx(tri('West China graduate education','华西研究生教育','Posgrado en West China'))+' ↗</a><a href="https://yz.scu.edu.cn/">'+self.tx(tri('Sichuan University admissions','四川大学研究生招生','Admisiones de la Universidad de Sichuan'))+' ↗</a></div></section>'
  return h
 def collaborate(self):
  h='<section class="section page-intro narrow">'+self.heading(self.tx(tri('Connect a question with complementary expertise.','让科学问题与互补的研究经验相遇。','Conectar preguntas y experiencia complementaria.')),self.tx(tri('We welcome conversations that connect brain-barrier biology, molecular design, imaging, and disease-related readouts. A clear shared question is the best starting point.','欢迎围绕脑屏障生物学、分子设计、成像及疾病相关读出开展交流。一个清楚的共同科学问题，是合作的起点。','Nos interesan conversaciones que conecten barreras cerebrales, diseño molecular, imagen y medidas relacionadas con enfermedades. El mejor punto de partida es una pregunta compartida.')),self.u('collaborate'))+'</section><section class="section">'+self.theme_cards()+'</section><section class="section join-grid"><div><h2>'+self.tx(tri('What could we investigate together?','可以共同探讨什么？','¿Qué podríamos investigar juntos?'))+'</h2><ul class="prose-list">'
  for x in [tri('Relating ligand or carrier design to barrier recognition and transport.','将配体或载体设计与屏障识别、运输行为联系起来。','Relacionar ligandos o vehículos con reconocimiento y transporte por barreras.'),tri('Matching a molecular probe or imaging readout to a biological question.','让分子探针或成像读出匹配具体生物学问题。','Adaptar una sonda o lectura de imagen a una pregunta biológica.'),tri('Connecting clearance pathways and cell states to disease or intervention studies.','将清除通路、细胞状态与疾病或干预研究相连接。','Conectar vías de eliminación y estados celulares con estudios de enfermedad o intervención.')]:h+='<li>'+self.tx(x)+'</li>'
  h+='</ul><p>'+self.tx(tri('Our publications show the methods and settings in which we have worked. Access to particular resources and the feasibility of a new project need to be discussed case by case.','已发表论文展示了我们参与过的方法和研究场景。具体资源使用与新项目可行性，需要逐项讨论。','Las publicaciones muestran métodos y contextos de nuestra experiencia. El acceso a recursos concretos y la viabilidad de cada proyecto se acuerdan caso por caso.'))+'</p>'+self.link('publications',self.u('allpapers'))+'</div><div class="callout"><h2>'+self.tx(tri('Start a conversation','发起合作交流','Iniciar una conversación'))+'</h2><p>'+self.tx(tri('Send a brief description of the question, the evidence or materials already available, and where our contributions might complement one another. We can then discuss scope, responsibilities, and a realistic next step.','请简述科学问题、已有证据或材料，以及双方可能互补的部分，再共同明确研究范围、责任分工和下一步工作。','Envía una descripción breve de la pregunta, la evidencia o los materiales disponibles y las posibles contribuciones complementarias. Después podremos acordar el alcance, las responsabilidades y el siguiente paso.'))+'</p>'+self.email('Tian Lab — collaboration enquiry')+'</div></section>'
  h+='<section class="section partnership partnership-text tinted"><div><p class="eyebrow">'+self.tx(tri('An established academic connection','已有学术合作','Un vínculo académico establecido'))+'</p><h2>IBEC Molecular Bionics</h2><p>'+self.tx(source['copy']['collabBody'])+'</p><a class="text-link" href="https://ibecbarcelona.eu/research-groups/molecular-bionics/">IBEC Molecular Bionics ↗</a></div></section>'
  h+='<section class="section venture"><div>'+self.img('./assets/images/adcerebri-logo.png','Adcerebri')+'</div><div><h2>Adcerebri · 安赛巴瑞</h2><p>'+self.tx(source['copy']['ventureLabel'])+'</p><p>'+self.tx(tri('For questions about translational research or a specific project, please contact the PI to discuss the appropriate connection.','如希望了解转化相关工作或具体项目，请联系 PI 沟通。','Para consultas sobre traslación o un proyecto concreto, contacta con el investigador principal.'))+'</p></div></section>'
  return h
 def news(self):
  h='<section class="section page-intro">'+self.heading(self.u('news'),self.tx(tri('Research updates and milestones from the lab.','课题组研究动态与阶段记录。','Actualizaciones e hitos del laboratorio.')))+'<div class="news-archive">'
  for i,n in enumerate(source['news']):
   # The old implementation-only update remains in the preserved source, not public news.
   if i==3:continue
   h+=f'<article id="news-{i+1}"><div class="date">{e(n["date"])}</div><div><h2>{self.tx(n["title"])}</h2>'
   if n.get('body'):h+='<p>'+self.tx(n['body'])+'</p>'
   target=n.get('href');target='publications.html#paper-snb-2026-ld-ttp' if target=='#publications' else target
   if target:h+=f'<a class="text-link" href="{e(target)}">{self.u("paper")} ↗</a>'
   else:h+=self.link('publications',self.u('covers'),'text-link','#covers')
   h+='</div></article>'
  return h+'</div></section>'
 def render(self,page):
  content=self.people_page() if page=='people' else getattr(self,page)()
  path=('' if self.lang=='en' else self.lang+'/')+('' if page=='index' else page+'.html')
  title='Tian Lab — '+self.u(page)
  langs=''.join(f'<a href="{self.prefix}{"" if l=="en" else l+"/"}{page}.html" lang="{l}" hreflang="{l}"'+(' aria-current="true"' if l==self.lang else '')+f'>{label}</a>' for l,label in [('en','English'),('zh','中文'),('es','Español')])
  nav=''.join('<a href="'+p+'.html"'+(' aria-current="page"' if p==page else '')+'>'+self.u(p)+'</a>' for p in ('research','publications','people','join','collaborate'))
  head=f'<!doctype html>\n<html lang="{"zh-CN" if self.lang=="zh" else self.lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><meta name="description" content="{self.tx(INTRO)}"><link rel="canonical" href="{BASE+path}">'
  for l in LANGS:head+=f'<link rel="alternate" hreflang="{"zh-CN" if l=="zh" else l}" href="{BASE}{"" if l=="en" else l+"/"}{"" if page=="index" else page+".html"}">'
  head+=f'<meta property="og:title" content="{title}"><meta property="og:description" content="{self.tx(INTRO)}"><meta property="og:type" content="website"><meta property="og:url" content="{BASE+path}"><meta property="og:image" content="{BASE}assets/images/sttt-2025-november-cover.jpg"><meta name="theme-color" content="#142829"><link rel="icon" type="image/svg+xml" href="{self.prefix}assets/favicon.svg"><link rel="stylesheet" href="{self.prefix}styles.css"><script src="{self.prefix}script.js" defer></script></head>'
  header=f'<body data-page="{page}"><a class="skip-link" href="#main">{self.u("skip")}</a><header class="site-header"><div class="header-inner"><a class="brand" href="index.html" aria-label="{self.tx(tri("Tian Lab home","Tian Lab 首页","Inicio de Tian Lab"))}"><span class="brand-mark" aria-hidden="true">T<span>↗</span></span><span>Tian Lab<small>{self.tx(tri("Brain barriers & molecular imaging","脑屏障与分子影像","Barreras cerebrales e imagen"))}</small></span></a><button class="menu-button" id="menu-toggle" type="button" aria-expanded="false" aria-controls="site-nav" hidden>{self.u("menu")} <span aria-hidden="true">☰</span></button><div id="site-nav"><nav aria-label="{self.u("navigation")}">{nav}</nav><nav class="language-nav" aria-label="{self.u("languages")}">{langs}</nav></div></div></header><main id="main" tabindex="-1">'
  footer='<footer class="site-footer"><div><a class="footer-brand" href="index.html">Tian Lab</a><p>'+self.tx(source['copy']['footerAffiliation'])+'<br>'+self.tx(source['copy']['footerCenter'])+'<br>'+self.u('location')+'</p></div><div><a href="mailto:'+e(self.contact['pi']['email'])+'">'+e(self.contact['pi']['email'])+'</a><div class="footer-links">'+self.link('join',self.u('join'),'')+self.link('collaborate',self.u('collaborate'),'')+self.link('news',self.u('news'),'')+'</div></div></footer></body></html>\n'
  return (head+header+content+'</main>'+footer).replace('><','>\n<')

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args();changed=[]
 for lang in LANGS:
  site=Site(lang)
  for page in PAGES:
   target=ROOT/('' if lang=='en' else lang)/(page+'.html');html=site.render(page)
   if args.check:
    if not target.exists() or target.read_text()!=html:changed.append(str(target.relative_to(ROOT)))
   else:target.parent.mkdir(parents=True,exist_ok=True);target.write_text(html)
 if changed:raise SystemExit('Out-of-date generated pages: '+', '.join(changed))
 print('21 static pages '+('match sources' if args.check else 'built'))
