const $ = id => document.getElementById(id);
const names = {baseline:'Baseline',tfidf:'TF-IDF',hybrid:'Hybrid','dense-wide':'Dense mở rộng','neighbors-1':'Hybrid + đoạn lân cận','neighbors-2':'Hybrid + lân cận rộng','reference-text':'Theo hình/bảng · text','reference-8':'Theo hình/bảng + ảnh','reference-12':'Theo hình/bảng + ảnh · rộng'};
let benchmark = {}, activeSplit = 'dev', status = {};
async function get(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error('Không đọc được dữ liệu.');
  return response.json();
}
function cell(row, text) {
  const td = document.createElement('td'); td.textContent = text; row.append(td); return td;
}
function renderBenchmark() {
  const advanced = $('dataset').value === 'advanced';
  const headers = advanced ? ['Cấu hình','Đạt / Tổng','Tỷ lệ','Thiếu bằng chứng đạt','Lỗi'] : ['Cấu hình','Điểm trả lời /2','Context đủ nguồn','Từ chối đúng','Lỗi'];
  $('benchmark-head').replaceChildren();
  for (const title of headers) { const th = document.createElement('th'); th.textContent = title; $('benchmark-head').append(th); }
  $('benchmark-note').textContent = advanced ? 'Bonus yêu cầu ít nhất 27/30 câu test đạt, gồm đủ mọi nhóm. Xem nhãn và lý do đối chiếu nguồn trong báo cáo.' : 'Điểm tối đa 2 cho câu có đáp án; nhãn API và bản rà nguồn được lưu riêng. Test cơ bản này là bộ mới sau cải thiện.';
  const body = $('benchmark-body'); body.replaceChildren();
  const rows = benchmark[activeSplit] || [];
  if (!rows.length) { const row = document.createElement('tr'); cell(row,'Chưa có kết quả đánh giá.').colSpan = 5; body.append(row); return; }
  for (const item of rows) {
    const row = document.createElement('tr'); const label = cell(row,names[item.configuration] || item.configuration);
    if (item.configuration === benchmark.selected) { const badge=document.createElement('span'); badge.className='selected-label'; badge.textContent='Đã chọn'; label.append(badge); }
    if (advanced) {
      cell(row,`${item.passed}/${item.total}`); cell(row,`${(100*item.rate).toFixed(1)}%`);
      const negative=item.by_group.unanswerable; cell(row,`${negative.n}/${negative.N}`); cell(row,String(item.errors));
    } else {
      const m=item.metrics; cell(row,m.answer_mean.toFixed(2)); cell(row,`${m.context_semantic.n}/${m.context_semantic.N}`);
      cell(row,`${m.abstention.n}/${m.abstention.N}`); cell(row,String(m.errors));
    }
    body.append(row);
  }
}
function renderAnswer(data) {
  $('answer-content').hidden=false; $('answer').replaceChildren();
  const sourceMap=new Map((data.sources||[]).map((source,index)=>[source.id,index]));
  let offset=0; const text=data.answer||data.reason||'Không có câu trả lời.';
  for (const match of text.matchAll(/\[([A-Za-z0-9_-]+)\]/g)) {
    if (!sourceMap.has(match[1])) continue;
    $('answer').append(document.createTextNode(text.slice(offset,match.index)));
    const index=sourceMap.get(match[1]), a=document.createElement('a'); a.href=`#source-${index}`; a.textContent=`[${index+1}]`; $('answer').append(a); offset=match.index+match[0].length;
  }
  $('answer').append(document.createTextNode(text.slice(offset)));
  $('reason').textContent=data.status==='abstain'?data.reason:'';
  const states={answered:'Có câu trả lời',abstain:'Chưa đủ bằng chứng',error:'Có lỗi'};
  $('answer-state').textContent=states[data.status]||data.status;
  $('answer-state').className='badge '+(data.status==='answered'?'success':data.status==='error'?'error':'');
  $('run-facts').replaceChildren();
  for (const value of [`${(data.elapsed_seconds||0).toFixed(1)} giây`,`${data.api_requests||0} lượt API`,`Ước tính $${(data.estimated_cost_upper_usd||0).toFixed(5)}`]) { const span=document.createElement('span'); span.textContent=value; $('run-facts').append(span); }
  $('sources').replaceChildren(); const imagePages=new Set();
  (data.sources||[]).forEach((source,index)=>{
    const detail=document.createElement('details'); detail.className='source'; detail.id=`source-${index}`;
    const summary=document.createElement('summary'); summary.textContent=`[${index+1}] Trang ${source.page} · ${source.metadata.reference||source.metadata.section_title||'Tài liệu nguồn'}`;
    const p=document.createElement('p'); p.textContent=source.text; detail.append(summary,p);
    if (source.page_image && /^\/api\/page\?page=\d+$/.test(source.page_image) && !imagePages.has(source.page)) {
      const img=document.createElement('img'); img.src=source.page_image; img.loading='lazy'; img.alt=`Ảnh gốc PDF trang ${source.page}`; detail.append(img); imagePages.add(source.page);
    }
    try { const url=new URL(source.source); if (['https:','http:'].includes(url.protocol)) { const a=document.createElement('a'); a.href=url.href; a.target='_blank'; a.rel='noopener noreferrer'; a.textContent='Mở tài liệu nguồn ↗'; detail.append(a); } } catch {}
    $('sources').append(detail);
  });
  $('searches').replaceChildren();
  for (const step of data.searches||[]) { const li=document.createElement('li'); li.textContent=`${step.query} — ${step.count} đoạn, trang ${step.pages.join(', ')||'không có'}`; $('searches').append(li); }
}
async function loadDataset(clear=false) {
  const dataset=$('dataset').value, advanced=dataset==='advanced';
  const info=(status.datasets||{})[dataset]||{};
  $('pages').textContent=`${info.pages||0} trang`; $('chunks').textContent=`${info.chunks||0} đoạn`;
  $('store-name').textContent=advanced?'DeepSeek Vision + vector local':'DeepSeek + pgvector Day 6';
  $('document-title').textContent=advanced?'NASA Systems Engineering Handbook, Rev 2. Đọc text, bảng, sơ đồ và biểu đồ; đối chiếu trực tiếp ảnh trang gốc.':'A General Introduction to Artificial Intelligence. Dùng dữ liệu Day 6 và context lân cận để giữ đủ ý.';
  const options=advanced?['selected','baseline','reference-text','reference-8','reference-12']:['selected','baseline','neighbors-1','neighbors-2','tfidf','hybrid','dense-wide'];
  $('configuration').replaceChildren(); for (const key of options) $('configuration').append(new Option(key==='selected'?'Cấu hình đã chọn từ dev':names[key],key));
  $('section').disabled=advanced; $('section').value=''; $('examples').replaceChildren();
  if (clear) { $('question').value=''; $('answer-content').hidden=true; $('empty').hidden=false; $('answer-state').textContent='Sẵn sàng'; }
  const examples=await get(`/api/examples?dataset=${dataset}`);
  if ($('dataset').value!==dataset) return;
  const labels={q01:'Hội nghị Dartmouth',q09:'Dữ liệu công nghiệp',dev_no_evidence_01:'Số tham số BERT',ad_t2:'Đọc bảng metadata',ad_c2:'Đọc biểu đồ',ad_n1:'Kiểm tra thiếu dữ liệu'};
  for (const example of examples) { const button=document.createElement('button'); button.type='button'; button.textContent=labels[example.id]||example.id; button.addEventListener('click',()=>{ $('question').value=example.question; $('section').value=example.filter.section||''; $('question').focus(); }); $('examples').append(button); }
  const result=await get(`/api/results?dataset=${dataset}`);
  if ($('dataset').value!==dataset) return;
  benchmark=result; renderBenchmark();
}
$('dataset').addEventListener('change',()=>loadDataset(true).catch(error=>renderAnswer({status:'error',reason:error.message})));
$('ask-form').addEventListener('submit',async event=>{
  event.preventDefault(); const question=$('question').value.trim(); if (!question) return;
  $('submit').disabled=true; $('dataset').disabled=true; $('loading').hidden=false; $('empty').hidden=true; $('answer-content').hidden=true; $('answer-state').textContent='Đang xử lý'; $('answer-state').className='badge';
  try {
    const filter=$('section').value?{section:$('section').value}:{};
    const response=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,dataset:$('dataset').value,configuration:$('configuration').value,filter})});
    const data=await response.json(); if (!response.ok) throw new Error(data.error||'Không xử lý được câu hỏi.'); renderAnswer(data);
  } catch (error) { renderAnswer({status:'error',reason:error.message}); }
  finally { $('submit').disabled=false; $('dataset').disabled=false; $('loading').hidden=true; }
});
for (const split of ['dev','test']) $(split+'-tab').addEventListener('click',()=>{ activeSplit=split; $('dev-tab').classList.toggle('active',split==='dev'); $('test-tab').classList.toggle('active',split==='test'); renderBenchmark(); });
(async()=>{ try { status=await get('/api/status'); $('connection').textContent=status.api_key_configured?'● DeepSeek đã cấu hình':'● Cần điền key trong .env'; $('connection').className='connection '+(status.api_key_configured?'ready':''); await loadDataset(); } catch (error) { $('connection').textContent='Không kết nối được máy chủ'; renderAnswer({status:'error',reason:error.message}); } })();
