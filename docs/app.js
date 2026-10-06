'use strict';
(async()=>{
 const ids=['search','country','category','source','sort','file'];
 const controls=Object.fromEntries(ids.map(id=>[id,document.getElementById(id)]));
 const tabs=[...document.querySelectorAll('[data-collection]')];
 const officialCards=[...document.querySelectorAll('#records .record')];
 let collection='grok';
 const safeUrl=value=>{try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:null;}catch{return null;}};
 const el=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
 const link=(url,text)=>{const node=el('a',text);node.href=safeUrl(url);node.target='_blank';node.rel='noopener noreferrer';return node;};
 const fill=(key,values,label)=>{controls[key].replaceChildren();const all=el('option',label);all.value='';controls[key].append(all);[...new Set(values.flat().filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-Hant')).forEach(value=>{const option=el('option',value);option.value=value;controls[key].append(option);});};
 try{
  const responses=await Promise.all(['data.json','grok.json'].map(url=>fetch(url)));if(responses.some(r=>!r.ok))throw Error('data unavailable');
  const [official,historical]=await Promise.all(responses.map(r=>r.json()));
  const data={official:official.items.map(x=>({...x,sortDate:x.date||(/^\d{4}-\d{2}$/.test(x.dates?.publication||'')?x.dates.publication:null),sources:[x.source],urls:[x.url]})),grok:historical.records};
  const host=document.getElementById('grok-records');
  const grokCards=data.grok.map(item=>{
   const card=el('article',undefined,'record unverified');card.dataset.id=item.id;
   const top=el('div',undefined,'record-top');top.append(el('span',item.verificationLabel,'badge'),el('span',`${item.country} · ${item.category}`));card.append(top);
   const heading=el('h2',item.title);card.append(heading);
   if(item.verifiedSummary){card.append(el('p',item.verifiedSummary,'summary'));card.append(el('p','本次依所列原文另寫的抽樣摘要','provenance'));}else if(item.summary){card.append(el('p',item.summary,'summary'));card.append(el('p',item.summaryAttribution||'附件摘要 · 尚未逐項查證','provenance'));}else card.append(el('p',item.summaryNote||'此筆僅作來源导航；原始敘述未公開。','provenance'));
   const dl=el('dl');[['附件原列日期（類型待辨）',item.sourceDateAsProvided||'未知'],...(item.verifiedPublicationDate?[['抽樣發布日期',item.verifiedPublicationDate]]:[]),['附件彙整日期',item.collectionDate||'未知'],['本次匯入日期',item.importedAt]].forEach(([name,value])=>{const row=el('div');row.append(el('dt',name),el('dd',value));dl.append(row);});card.append(dl);
   const detail=el('details');detail.append(el('summary','來源、日期與抽樣查證範圍'));
   detail.append(el('p',`匯入出處：${item.provenance.fileName}，CSV 第 ${item.provenance.csvRow} 列（含標頭）`));detail.append(el('p',item.collectionDateNote));detail.append(el('p','附件檔名不是來源截止日期；附件原列日期可能是發布、事件或生效日，尚未一律獨立核實。'));if(item.sourceDatePrecision==='month')detail.append(el('p','附件日期僅精確至月份；排序時依月份排列，不補造日期。'));detail.append(el('p','本次資料整理截至 2026-10-05；同一網址可能改版或更正，請回原文確認。'));
   if(item.verifiedPublicationDate)detail.append(el('p',`抽樣查得的發布日期：${item.verifiedPublicationDate}`));if(item.verifiedEventDate)detail.append(el('p',`事件／生效日期：${item.verifiedEventDate}`));(item.sampleNotes||[]).forEach(note=>detail.append(el('p',note)));
   if(item.duplicateUrlCount)card.append(el('p',`同址提醒：與其他 ${item.duplicateUrlCount} 筆共用來源；不算獨立佐證。`,'revision-note'));
   if(item.verifiedSummary&&item.summary){detail.append(el('p','附件摘要安全節錄（未逐項核實，與上方本次抽樣摘要分開保留）：'));detail.append(el('p',item.summary));}card.append(detail);const links=el('div',undefined,'reference-links');item.urls.filter(safeUrl).forEach((url,index)=>links.append(link(url,`${index+1}. ${new URL(url).hostname.replace(/^www\./,'')}`)));card.append(links);host.append(card);return card;
  });
  const cards={official:officialCards,grok:grokCards};
  const apply=()=>{const query=controls.search.value.trim().toLocaleLowerCase();let count=0;const items=data[collection];
   cards[collection].forEach(card=>{const item=items.find(x=>x.id===card.dataset.id);const visible=!!item&&(!controls.country.value||item.country===controls.country.value)&&(!controls.category.value||item.category===controls.category.value)&&(!controls.source.value||item.sources.includes(controls.source.value))&&(!controls.file.value||item.provenance?.fileName===controls.file.value)&&(!query||[item.title,item.original,item.summary,item.verifiedSummary,...item.sources,item.country,item.category].join(' ').toLocaleLowerCase().includes(query));card.hidden=!visible;if(visible)count++;});
   const byId=new Map(items.map(x=>[x.id,x]));const ordered=[...cards[collection]].sort((a,b)=>{const x=byId.get(a.dataset.id).sortDate,y=byId.get(b.dataset.id).sortDate;if(!x&&!y)return a.dataset.id.localeCompare(b.dataset.id);if(!x)return 1;if(!y)return -1;return controls.sort.value==='oldest'?x.localeCompare(y):y.localeCompare(x);});
   const container=document.getElementById(collection==='official'?'records':'grok-records');ordered.forEach(card=>container.append(card));
   document.getElementById('count').textContent=`顯示 ${count} / ${items.length} 筆 · 未知日期置後`;
   document.getElementById('empty').hidden=count!==0;
  };
  const switchCollection=value=>{collection=value;tabs.forEach(tab=>tab.setAttribute('aria-pressed',String(tab.dataset.collection===value)));document.getElementById('records').hidden=value!=='official';host.hidden=value!=='grok';controls.search.value='';fill('country',data[value].map(x=>x.country),'全部地區');fill('category',data[value].map(x=>x.category),'全部主題');fill('source',data[value].map(x=>x.sources),'全部來源');fill('file',data[value].map(x=>x.provenance?.fileName),'全部4份CSV');controls.file.hidden=value!=='grok';document.getElementById('file-label').hidden=value!=='grok';document.getElementById('sort-label').textContent=value==='official'?'排序依據：卡片標示日期（發布／更新／更正分開標示）':'排序依據：附件原列日期（可能為事件或生效日，未補造缺失日期）';document.getElementById('collection-description').textContent=value==='official'?`已核對官方網頁的 ${data.official.length} 筆選讀；研究報告不等同生效政策。`:`4份CSV整併為 ${data.grok.length} 筆公開線索，共用搜尋、來源及日期排序；原檔名與列號保留。抽樣核對僅限註記欄位，其餘待查證。`;apply();};
  ids.forEach(id=>controls[id].addEventListener(id==='search'?'input':'change',apply));tabs.forEach(tab=>tab.addEventListener('click',()=>switchCollection(tab.dataset.collection)));
  document.getElementById('reset').addEventListener('click',()=>{['search','country','category','source','file'].forEach(id=>controls[id].value='');controls.sort.value='newest';apply();});switchCollection('grok');
 }catch{document.getElementById('load-error').hidden=false;ids.forEach(id=>controls[id].disabled=true);tabs.forEach(tab=>tab.disabled=true);document.getElementById('reset').disabled=true;}
})();
