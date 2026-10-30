'use strict';
const types={
  'Parc national':'#26634d','PNR':'#7b9452','Parc naturel':'#3e8b7d',
  'Parc naturel marin':'#31849b','Site classé':'#9c9272',
  'Réserve naturelle':'#ac785b','Réserve biologique':'#936d9f','Natura 2000':'#528db8',
  'Site de conservatoire':'#b59c45','Conservatoire du littoral':'#5bafb1',
  'Arrêté de protection':'#b96e81','Périmètre de protection':'#a68c79',
  'Reconnaissance internationale':'#8583aa','Autre protection':'#8b9590','Projet de PNR':'#c39135'
};
const el=id=>document.getElementById(id);
const text=(tag,value,className)=>{const n=document.createElement(tag);n.textContent=value;if(className)n.className=className;return n;};
const quality=p=>p.evidence||((p.id||'').startsWith('osm:')?'osm':'reference');
const qualityLabel=p=>quality(p)==='official'?'Contour officiel':quality(p)==='osm'?'Source OSM':'Repère indicatif';
const normalize=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('fr');
function safeLink(url,label){try{const u=new URL(url);if(!['https:','http:'].includes(u.protocol))return null;const a=text('a',label);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{return null;}}
function date(value){if(!value)return 'Non renseignée';const d=new Date(String(value).replace(/Z$/,'').slice(0,10));return Number.isNaN(d.getTime())?String(value):d.toLocaleDateString('fr-FR',{timeZone:'UTC'});}
let data,visible=[],selectedId=null,selectedButton=null,layerGroup;
const layers=new Map();
const map=L.map('map',{zoomControl:false,preferCanvas:true,minZoom:5}).setView([42.8,.7],7);
L.control.zoom({position:'bottomright'}).addTo(map);
L.control.scale({position:'bottomright',imperial:false}).addTo(map);
const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map);
let tileFailure=false;
tiles.on('tileerror',()=>{if(tileFailure)return;tileFailure=true;el('map-caption').textContent='Fond indisponible — contours et fiches restent consultables';});
function switchView(view){document.body.dataset.view=view;el('view-map').setAttribute('aria-pressed',String(view==='map'));el('view-list').setAttribute('aria-pressed',String(view==='list'));if(view==='map')requestAnimationFrame(()=>map.invalidateSize());}
el('view-map').onclick=()=>switchView('map');el('view-list').onclick=()=>switchView('list');
function resetExtent(){map.fitBounds([[42,-2],[43.6,3.5]],{padding:[25,25],animate:false});}
el('fit').onclick=resetExtent;
function closeDetail(){el('detail').hidden=true;selectedId=null;if(selectedButton)selectedButton.setAttribute('aria-pressed','false');selectedButton=null;}
el('detail-close').onclick=()=>{const button=selectedButton;closeDetail();if(button&&document.body.dataset.view==='list')button.focus();};
function show(feature,button){
 const p=feature.properties;selectedId=p.id;if(selectedButton)selectedButton.setAttribute('aria-pressed','false');selectedButton=button||document.querySelector(`[data-feature-id="${CSS.escape(p.id)}"]`);if(selectedButton)selectedButton.setAttribute('aria-pressed','true');
 const body=el('detail-body');body.replaceChildren();const eyebrow=text('div',p.category+' · '+(p.country||'Pays non renseigné'),'detail-eyebrow');const dot=text('span','','swatch');dot.style.background=types[p.category]||'#777';eyebrow.prepend(dot);const title=text('h2',p.name);title.id='detail-title';const badge=text('span',p.status==='Projet'?'Projet · sans contour de classement':qualityLabel(p),'detail-badge'+(quality(p)!=='official'?' indicative':''));body.append(eyebrow,title,badge);
 const dl=document.createElement('dl');
 const fields={'Désignation':p.designation||p.category,'Gestionnaire':p.operator||'Non renseigné','Référence':p.reference||p.id,'Statut dans la source':p.status,'Géométrie':p.geometry_quality==='official_simplified'?'Contour officiel simplifié (~4–6 m)':feature.geometry.type==='Point'?'Point indicatif, sans contour':'Contour fourni par la source'};
 if(p.source_modified)fields['Mise à jour source']=date(p.source_modified);
 if(p.source_term_end)fields['Échéance renseignée (à vérifier)']=date(p.source_term_end);
 fields['Date de collecte']=p.collected_at?date(p.collected_at):'Vérification en ligne en attente';
 for(const [key,value] of Object.entries(fields))dl.append(text('dt',key),text('dd',value));
 body.append(dl);if(p.note)body.append(text('p',p.note));const links=text('div','','detail-links');
 if(p.url){const a=safeLink(p.url,'Consulter la fiche source');if(a)links.append(a);}
 if(p.source_download){const a=safeLink(p.source_download,'Contour original · GeoJSON');if(a)links.append(a);}
 body.append(links,text('p',p.source+(p.license?' · '+p.license:''),'detail-source'));
 el('detail').hidden=false;el('detail').scrollTop=0;
 if(matchMedia('(max-width:720px)').matches)switchView('map');
 const layer=layers.get(p.id);
 if(layer){const mobile=matchMedia('(max-width:720px)').matches;const options={maxZoom:12,paddingTopLeft:[30,90],paddingBottomRight:mobile?[30,Math.min(380,map.getSize().y*.55)]:[365,40]};if(layer.getBounds&&layer.getBounds().isValid())map.fitBounds(layer.getBounds(),options);else if(layer.getLatLng)map.setView(layer.getLatLng(),10);}
}
function render(){
 if(!data)return;
 closeDetail();if(layerGroup)map.removeLayer(layerGroup);layers.clear();layerGroup=L.featureGroup().addTo(map);
 const chosen=new Set([...document.querySelectorAll('#filters input:checked')].map(n=>n.value));
 const query=normalize(el('search').value),country=el('country').value,evidence=el('quality').value;
 visible=data.features.filter(f=>{const p=f.properties;return chosen.has(p.category)&&(!country||(p.country||'').split(' / ').includes(country))&&(!evidence||quality(p)===evidence)&&normalize([p.name,p.operator,p.reference,p.designation].join(' ')).includes(query);});
 const priority=['Parc national','PNR','Parc naturel','Parc naturel marin','Projet de PNR','Réserve naturelle','Réserve biologique','Natura 2000','Site de conservatoire','Conservatoire du littoral','Arrêté de protection','Périmètre de protection','Reconnaissance internationale','Site classé','Autre protection'];
 visible.sort((a,b)=>priority.indexOf(a.properties.category)-priority.indexOf(b.properties.category)||a.properties.name.localeCompare(b.properties.name,'fr'));
 const list=el('results');list.replaceChildren();const fragment=document.createDocumentFragment();
 // Larger polygons first; small reserves and sites stay clickable above regional parks.
 const ordered=[...visible].sort((a,b)=>(b.properties.source_area_ha||0)-(a.properties.source_area_ha||0));
 for(const feature of ordered){const p=feature.properties,color=types[p.category]||'#888';const layer=L.geoJSON(feature,{style:{color,weight:1.4,fillOpacity:.12,dashArray:p.status==='Projet'?'5 4':null},pointToLayer:(_,ll)=>L.circleMarker(ll,{radius:6,color,fillColor:'#fff',weight:2,fillOpacity:1})}).addTo(layerGroup);layer.bindTooltip(text('span',p.name),{sticky:true});layer.on('click',()=>show(feature));layers.set(p.id,layer);}
 for(const feature of visible){const p=feature.properties;const li=document.createElement('li'),button=text('button','','result-card');button.dataset.featureId=p.id;button.setAttribute('aria-pressed','false');const top=text('div','','result-top'),swatch=text('span','','swatch');swatch.style.background=types[p.category]||'#777';top.append(swatch,document.createTextNode(p.category));const bottom=text('div','','result-bottom');bottom.append(text('span',p.country||'Pays non renseigné'),text('span','','quality-dot'),text('span',p.status==='Projet'?'En projet':qualityLabel(p)));const arrow=text('span','','arrow');arrow.setAttribute('aria-hidden','true');arrow.innerHTML='<svg viewBox="0 0 24 24"><path d="M5 12h14m-5-5 5 5-5 5"/></svg>';button.append(top,text('h2',p.name),bottom,arrow);button.onclick=()=>show(feature,button);li.append(button);fragment.append(li);}
 list.append(fragment);if(!visible.length)list.append(text('li','Aucun espace ne correspond. Essayez un autre filtre.','empty-state'));
 const projects=visible.filter(f=>f.properties.status==='Projet').length;el('count').textContent=`${visible.length.toLocaleString('fr-FR')} enregistrements${projects?' · '+projects+' projet':''}`;el('type-count').textContent=`${chosen.size} / ${Object.keys(types).length}`;
}
for(const [name,color] of Object.entries(types)){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=name;input.checked=true;input.onchange=render;const swatch=text('span','','swatch');swatch.style.background=color;const total=text('span','','type-total');total.dataset.category=name;label.append(input,swatch,document.createTextNode(name),total);el('filters').append(label);}
let searchTimer;el('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(render,140);};el('country').onchange=render;el('quality').onchange=render;
function selectTypes(checked){document.querySelectorAll('#filters input').forEach(n=>n.checked=checked);render();}el('types-all').onclick=()=>selectTypes(true);el('types-none').onclick=()=>selectTypes(false);
el('reset').onclick=()=>{el('search').value='';el('country').value='';el('quality').value='';selectTypes(true);};
el('export').onclick=()=>{if(!data)return;const output={...data,metadata:{...data.metadata,exported_at:new Date().toISOString(),selection_records:visible.length},features:visible};const url=URL.createObjectURL(new Blob([JSON.stringify(output)],{type:'application/geo+json'}));const a=document.createElement('a');a.href=url;a.download='pyrenees-selection.geojson';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
function method(){el('method-dialog').showModal();}el('method-open').onclick=method;el('legend-method').onclick=method;el('method-close').onclick=()=>el('method-dialog').close();el('method-dialog').onclick=e=>{if(e.target===el('method-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}};
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!el('method-dialog').open)closeDetail();});
fetch('data/areas.geojson').then(r=>{if(!r.ok)throw new Error(r.status);return r.json();}).then(value=>{data=value;el('notice').textContent=data.metadata.notice;el('provenance').textContent=data.metadata.provenance;
 const totals=new Map();for(const f of data.features)totals.set(f.properties.category,(totals.get(f.properties.category)||0)+1);document.querySelectorAll('.type-total').forEach(n=>n.textContent=totals.get(n.dataset.category)||0);
 el('france-coverage').textContent=`${data.metadata.official_records||0} contours officiels INPN / PatriNat, diffusés par l’IGN. ${data.metadata.france_layers?.length||0} couches collectées.`;
 for(const source of data.metadata.france_layers||[]){const row=document.createElement('tr');row.append(text('td',source.designation),text('td',source.records),text('td',date(source.collected_at)));el('source-table').append(row);}render();resetExtent();
}).catch(error=>{el('notice').textContent='Données indisponibles : rechargez la page ou consultez le dépôt du projet.';el('count').textContent='Chargement impossible';console.error(error);});
