(() => {
  'use strict';
  const book = window.STORY_BOOK, audio = window.STORY_AUDIO;
  const narration = book.book.chapter_narration !== false;
  const words = new Map(book.vocabulary.map(w => [w.word_id, w]));
  const $ = id => document.getElementById(id);
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const normalize = value => value.normalize('NFKC').trim().toLowerCase().replace(/\s+/g, ' ');
  const marker = /\[\[([^|\]]+)\|([^\]]+)\]\]/g;
  let chapterIndex = 0, mode = 'mixed', activeWord;
  const guided = Array.isArray(book.book.learning_path);
  const reviewPrompts = new Map((book.review_prompts || []).map(p => [p.word_id, p]));
  const drafts = new Map(), lastGrades = new Map(), finishedChapters = new Set();
  const retrySessions = new Map();
  let recallContext = 'story', answerScope = 'all';
  const player = $('chapterAudio');
  const wordPlayer = new Audio();
  window.__wordAudio = wordPlayer;
  const chapter = () => book.chapters[chapterIndex];
  const planned = () => [...chapter().new_word_ids, ...chapter().review_word_ids];
  const retrySession = () => retrySessions.get(chapter().chapter_id);
  const isRetry = () => guided && retrySession()?.mode === mode && (mode !== 'meaning' || retrySession().context === recallContext);
  const exerciseIds = () => isRetry() ? planned().filter(id => retrySession().ids.has(id)) : planned();
  const usingTransfer = () => mode === 'meaning' ? recallContext === 'transfer' : mode === 'answers' && lastGrades.get(chapter().chapter_id)?.context === 'transfer';
  const plain = text => text.replace(marker, (_, id, meaning) => `${words.get(id).lemma}（${meaning}）`);
  const context = id => {
    if (usingTransfer() && reviewPrompts.has(id)) return reviewPrompts.get(id).sentence;
    const p = chapter().paragraphs.find(p => p.mixed.includes(`[[${id}|`));
    return p ? plain(p.mixed) : '';
  };
  const token = (id, surface) => `<button type="button" class="word-token" data-word="${escape(id)}" lang="en">${escape(surface || words.get(id).lemma)}</button>`;
  const info = {
    mixed: ['跟着故事，走进词的语境', '点击绿色英文词，查看本句释义与用法。读完后再试着回忆。'],
    vocabulary: ['本章的词，一起认一遍', '释义只取本次故事中的义项；复现词会单独标记。'],
    meaning: ['看见英文，想起中文', '填写本句中英文词的中文义。按所学义项核对，参考答案在「答案讲解」。'],
    spelling: ['留下提示，自己拼出来', '根据中文提示填写词表原形；不区分大小写，忽略首尾空格。'],
    english: ['再用英语，把故事读一遍', narration ? '英语采用自然词形。点击单词查词卡；音频生成后可按段落播放。' : '英语采用自然词形。点击英文词查看词卡。'],
    answers: ['把答案放回语境里', '对照原句理解词义和搭配，再回到练习检验一次。']
  };
  function mixedParagraph(text, index) {
    let occurrence = 0;
    return escape(text).replace(/\[\[([^|\]]+)\|([^\]]+)\]\]/g, (_, id, meaning) => {
      const w = words.get(id);
      if (mode === 'mixed') return `${token(id)}<span class="word-gloss">（${escape(w.sense_zh)}）</span>`;
      if (isRetry() && !retrySession().ids.has(id)) return `${token(id)}<span class="word-gloss">（${escape(w.sense_zh)}）</span>`;
      const label = mode === 'spelling' ? `${w.sense_zh}的英文原形` : `${w.lemma} 的中文词义`;
      const answer = mode === 'spelling' ? w.lemma : w.sense_zh;
      const field = `<input class="exercise-input" id="answer-${index}-${occurrence++}" data-answer="${escape(answer)}" data-word-id="${id}" aria-label="${escape(label)}" autocomplete="off" spellcheck="false" placeholder="${mode === 'spelling' ? '填英文原形' : '填中文义'}">`;
      return mode === 'spelling' ? `${field}<span class="word-gloss">（${escape(w.sense_zh)}）</span>` : `${token(id)} ${field}`;
    });
  }
  function englishParagraph(text) {
    const mapping = new Map();
    planned().forEach(id => words.get(id).forms.forEach(form => mapping.set(form.toLowerCase(), id)));
    const pattern = [...mapping.keys()].sort((a,b) => b.length-a.length).map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const regex = new RegExp(`\\b(${pattern})\\b`, 'gi');
    let result = '', start = 0;
    for (const match of text.matchAll(regex)) {
      result += escape(text.slice(start, match.index)) + token(mapping.get(match[0].toLowerCase()), match[0]);
      start = match.index + match[0].length;
    }
    return result + escape(text.slice(start));
  }
  function comprehension() {
    return `<section class="comprehension"><h3>读懂了吗？</h3>${chapter().questions.map(q => `<fieldset><legend>${escape(q.prompt)}</legend>${q.options.map((option, i) => `<label><input type="radio" name="${q.question_id}" value="${i}"> ${escape(option)}</label>`).join('')}<p class="question-feedback" id="feedback-${q.question_id}" role="status"></p></fieldset>`).join('')}<button type="button" id="checkComprehension" class="plain-button">检查理解题</button></section>`;
  }
  const draftKey = () => `${chapter().chapter_id}:${mode}:${mode === 'meaning' ? recallContext : 'story'}${isRetry() ? ':retry' : ''}`;
  function rememberDraft() {
    if (!guided) return;
    if (mode === 'mixed') {
      drafts.set(draftKey(), {questions:chapter().questions.map(q => ({id:q.question_id,value:document.querySelector(`input[name="${q.question_id}"]:checked`)?.value,feedback:$(`feedback-${q.question_id}`)?.textContent || ''}))});
      return;
    }
    if (!['meaning','spelling'].includes(mode)) return;
    const state = drafts.get(draftKey()) || {};
    state.values = [...document.querySelectorAll('input[data-answer]')].map(e => e.value);
    drafts.set(draftKey(), state);
  }
  function restoreDraft() {
    if (!guided) return;
    const state = drafts.get(draftKey());
    if (!state) return;
    if (mode === 'mixed') {
      for (const q of state.questions || []) {
        if (q.value !== undefined) document.querySelector(`input[name="${q.id}"][value="${q.value}"]`).checked = true;
        $(`feedback-${q.id}`).textContent = q.feedback;
      }
      return;
    }
    document.querySelectorAll('input[data-answer]').forEach((e,i) => {
      e.value = state.values?.[i] || '';
      if (state.checked) e.setAttribute('aria-invalid', String(!state.correct[i]));
    });
    if (state.checked) $('exerciseResult').textContent = state.message;
  }
  function updatePath() {
    $('learningPath').hidden = !guided;
    if (!guided) return;
    const step = ['meaning','spelling'].includes(mode) ? 'meaning' : mode === 'answers' ? 'answers' : 'mixed';
    document.querySelectorAll('[data-step]').forEach(b => b.setAttribute('aria-current', String(b.dataset.step === step)));
    $('sessionProgress').textContent = `本次会话已结束 ${finishedChapters.size} / ${book.chapters.length} 章`;
    $('guidedNext').textContent = step === 'mixed' ? '开始词义回忆' : step === 'meaning' ? '核对并看解释' : '结束本章';
    $('sessionEnd').hidden = !finishedChapters.has(chapter().chapter_id);
    $('continueChapter').disabled = chapterIndex === book.chapters.length-1;
    $('continueChapter').textContent = chapterIndex === book.chapters.length-1 ? '已到最后一章' : '继续下一章';
  }
  function changeMode(next) {
    rememberDraft(); mode = next; renderContent();
  }
  function gradeAnswers() {
    const inputs = [...document.querySelectorAll('input[data-answer]')];
    let correct = 0, answered = 0;
    const results = [], needs = new Set();
    inputs.forEach(input => {
      const value = normalize(input.value), w = words.get(input.dataset.wordId);
      const accepted = [input.dataset.answer, ...(mode === 'meaning' ? w.meaning_answers || [] : [])].map(normalize);
      const ok = accepted.includes(value);
      if(value) answered++; if(ok) correct++; else needs.add(w.word_id);
      results.push(ok); input.setAttribute('aria-invalid', String(!ok));
    });
    const message = `${correct} / ${inputs.length} 处正确，已填写 ${answered} 处。${correct === inputs.length ? '做得好，再看看英文故事里的词形。' : '红框处可重新尝试；答案和用法见「答案讲解」。'}`;
    $('exerciseResult').textContent = message;
    if (guided) {
      drafts.set(draftKey(), {values:inputs.map(e=>e.value),correct:results,checked:true,message});
      const retry = isRetry();
      lastGrades.set(chapter().chapter_id, {key:draftKey(),mode,context:mode === 'meaning' ? recallContext : 'story',retry,needs,correct,total:inputs.length});
      if (!retry) retrySessions.delete(chapter().chapter_id);
      answerScope = 'needs';
    }
  }
  function renderContent() {
    const c = chapter();
    $('modeTitle').textContent = info[mode][0];
    $('modeHelp').textContent = info[mode][1];
    if (isRetry()) $('modeHelp').textContent = '只重练上次错词和未答词，题型与语境保持一致；整章原作答另行保留。';
    document.querySelectorAll('[data-mode]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.mode === mode)));
    $('exerciseActions').hidden = !['meaning', 'spelling'].includes(mode);
    $('exerciseResult').textContent = '';
    $('recallTools').hidden = !guided || mode !== 'meaning' || reviewPrompts.size !== words.size || isRetry();
    $('recallContext').value = recallContext;
    $('answerTools').hidden = !guided || mode !== 'answers';
    $('answerScope').value = answerScope;
    $('retryTools').hidden = !isRetry();
    if (isRetry()) $('retrySummary').textContent = `本轮仅重练 ${exerciseIds().length} 词 · ${mode === 'spelling' ? '拼写' : recallContext === 'transfer' ? '新语境词义' : '故事词义'} · 整章原作答保留`;
    let html = '';
    if (mode === 'vocabulary') {
      html = `<div class="table-container"><table class="vocab-table"><thead><tr><th>单词 / 发音</th><th>本句释义与用法</th></tr></thead><tbody>${planned().map(id => {
        const w = words.get(id), review = c.review_word_ids.includes(id);
        return `<tr><td><span class="lemma">${token(id)}</span><span class="ipa">${escape(w.ipa)}</span><span class="${review ? 'tag-review' : 'tag-new'}">${review ? '复现' : '新词'}</span> <button type="button" class="vocab-audio" data-word-audio="${id}" aria-label="听 ${w.lemma} 发音" ${audio.words[id] ? '' : 'disabled'}>${audio.words[id] ? '▶ 点读' : '配音待做'}</button></td><td><strong>${escape(w.pos)} ${escape(w.sense_zh)}</strong><p>${escape(w.explanation)}</p><p class="usage-note">${escape(context(id))}</p><small>${escape(w.source)} · ${escape(w.source_version)}</small></td></tr>`;
      }).join('')}</tbody></table></div>`;
    } else if (mode === 'english') {
      html = c.paragraphs.map((p, i) => `<section class="english-section" id="paragraph-${p.paragraph_id}"><div class="paragraph-tools"><span>PARAGRAPH ${String(i+1).padStart(2,'0')}</span>${narration ? `<button type="button" data-paragraph-play="${p.paragraph_id}" ${audio.chapters[c.chapter_id] ? '' : 'disabled'} aria-label="播放第 ${i+1} 段">▶ ${audio.chapters[c.chapter_id] ? '从此段播放' : '配音待做'}</button>` : ''}</div><p class="english-paragraph" lang="en">${englishParagraph(p.english)}</p></section>`).join('');
    } else if (mode === 'answers') {
      const grade = guided ? lastGrades.get(c.chapter_id) : undefined;
      const ids = grade && answerScope === 'needs' ? planned().filter(id => grade.needs.has(id)) : planned();
      const attempt = grade?.retry ? '本轮重练' : '本次';
      $('answerSummary').textContent = !grade ? '尚未核对回忆，先展示本章全部。' : !grade.needs.size ? `${attempt}均答对；可切换查看全部答案，之后再做回顾。` : `${attempt} ${grade.correct} / ${grade.total} 处正确，${grade.needs.size} 词待巩固（含未答）。`;
      $('retryNeeds').disabled = !grade?.needs.size;
      $('retryNeeds').textContent = grade?.needs.size ? `只重练待巩固 ${grade.needs.size} 词` : '只重练待巩固词';
      html = `<ol class="answer-list">${ids.map(id => { const w = words.get(id); const note = grade?.context === 'transfer' ? reviewPrompts.get(id)?.explanation_zh || w.explanation : w.explanation; return `<li data-answer-word="${id}">${token(id)} <strong>${escape(w.pos)} ${escape(w.sense_zh)}</strong><p>${escape(note)}</p><blockquote>${escape(context(id))}</blockquote></li>`; }).join('')}</ol><section class="comprehension"><h3>理解题答案</h3>${c.questions.map(q => `<p><strong>${escape(q.prompt)}</strong><br>${escape(q.options[q.answer_index])}。${escape(q.explanation)}（${escape(q.evidence_paragraph_id)}）</p>`).join('')}</section>`;
    } else if (mode === 'meaning' && recallContext === 'transfer' && reviewPrompts.size === words.size) {
      html = exerciseIds().map(id => {
        const w = words.get(id), prompt = reviewPrompts.get(id);
        return `<section class="recall-card" data-word-id="${id}" data-introduction="${c.new_word_ids.includes(id) ? 'new' : 'review'}"><p lang="en">${englishParagraph(prompt.sentence)}</p><label>${escape(w.lemma)} 的中文词义 <input class="exercise-input" data-word-id="${id}" data-answer="${escape(w.sense_zh)}" aria-label="${escape(w.lemma)} 的中文词义" autocomplete="off" spellcheck="false" placeholder="填写本句中文义"></label></section>`;
      }).join('');
    } else {
      html = c.paragraphs.map((p, i) => isRetry() && ![...p.mixed.matchAll(marker)].some(m => retrySession().ids.has(m[1])) ? '' : `<p class="story-paragraph">${mixedParagraph(p.mixed, i)}</p>`).join('');
      if (mode === 'mixed') html += comprehension();
    }
    $('readingContent').innerHTML = html;
    restoreDraft(); updatePath();
  }
  function time(value) { const n = Math.max(0, Math.floor(value || 0)); return `${Math.floor(n/60)}:${String(n%60).padStart(2,'0')}`; }
  function updateAudio() {
    if (!narration) return;
    const meta = audio.chapters[chapter().chapter_id];
    const duration = Number.isFinite(player.duration) ? player.duration : meta?.duration || 0;
    $('audioTime').textContent = `${time(player.currentTime)} / ${time(duration)}`;
    $('audioSeek').value = duration ? player.currentTime / duration * 100 : 0;
    $('chapterPlay').setAttribute('aria-label', player.paused ? '播放本章英文' : '暂停本章英文');
    $('chapterPlay').innerHTML = `<span aria-hidden="true">${player.paused ? '▶' : 'Ⅱ'}</span><span>${player.paused ? '英文朗读' : '暂停朗读'}</span>`;
    const cue = meta?.cues.find(p => player.currentTime >= p.start && player.currentTime < p.end);
    document.querySelectorAll('.english-section').forEach(p => p.classList.toggle('is-playing', !player.paused && p.id === `paragraph-${cue?.paragraph_id}`));
  }
  async function playChapter() {
    if (!narration) return;
    if (!audio.chapters[chapter().chapter_id]) return;
    wordPlayer.pause();
    try { await player.play(); $('audioStatus').textContent = '英文朗读 · 豆包 AI 配音'; }
    catch { $('audioStatus').textContent = '播放失败，请确认音频文件与页面一起解压。'; }
  }
  function showChapter(index) {
    rememberDraft();
    chapterIndex = index;
    if (guided) mode = 'mixed';
    const c = chapter();
    wordPlayer.pause();
    if (narration) {
      player.pause(); player.removeAttribute('src'); player.load();
      const meta = audio.chapters[c.chapter_id];
      if (meta) player.src = meta.file;
      player.playbackRate = Number($('audioSpeed').value);
      $('chapterPlay').disabled = !meta; $('audioSeek').disabled = !meta; $('audioSpeed').disabled = !meta;
      $('audioStatus').textContent = meta ? '英文朗读已生成 · 点击播放' : '英文朗读未生成 · 配音待做';
    }
    $('chapterKicker').textContent = `CHAPTER ${String(index+1).padStart(2,'0')} / ${book.chapters.length}`;
    $('chapterTitle').textContent = c.title; $('chapterSummary').textContent = c.summary;
    $('chapterTags').innerHTML = `<span>${c.new_word_ids.length} 个新词</span><span>${c.review_word_ids.length} 个复现词</span><span>${c.paragraphs.length} 段故事</span>`;
    document.querySelectorAll('[data-chapter]').forEach(b => b.setAttribute('aria-current', String(b.dataset.chapter === c.chapter_id)));
    $('previousChapter').disabled = index === 0; $('nextChapter').disabled = index === book.chapters.length-1;
    $('footerChapter').textContent = `${index+1} / ${book.chapters.length}`;
    renderContent(); updateAudio();
  }
  function openWord(id, play = false) {
    activeWord = id;
    const w = words.get(id);
    $('wordTitle').textContent = w.lemma; $('wordIpa').textContent = w.ipa;
    $('wordMeaning').textContent = `${w.pos} ${w.sense_zh}`; $('wordContext').textContent = context(id);
    $('wordExplanation').textContent = usingTransfer() ? reviewPrompts.get(id)?.explanation_zh || w.explanation : w.explanation;
    $('wordPlay').disabled = !audio.words[id];
    $('wordAudioStatus').textContent = audio.words[id] ? '豆包 AI 配音 · 点击播放' : '单词发音未生成 · 配音待做';
    if (!$('wordDialog').open) $('wordDialog').showModal();
    if (play) playWord();
  }
  async function playWord() {
    const meta = audio.words[activeWord];
    if (!meta) return;
    player?.pause(); wordPlayer.pause(); wordPlayer.src = meta.file;
    try { await wordPlayer.play(); $('wordAudioStatus').textContent = '正在播放'; }
    catch { $('wordAudioStatus').textContent = '播放失败，请检查音频文件。'; }
  }
  $('bookTitle').textContent = book.book.title; $('bookSubtitle').textContent = book.book.subtitle;
  $('vocabularySummary').innerHTML = `${escape(book.book.level_label || '故事词汇学习包')}<br>${book.vocabulary.length} 个目标词 · 本包学习范围`;
  $('chapterCount').textContent = `${book.chapters.length} CHAPTERS`;
  if (guided) document.querySelector('.reading-guide small').textContent = '作答与结束标记只保留在本次页面会话，刷新清空。';
  document.title = `${book.book.title} · 读词`;
  $('chapterList').innerHTML = book.chapters.map((c,i) => `<button type="button" class="chapter-choice" data-chapter="${c.chapter_id}"><span class="chapter-number">${String(i+1).padStart(2,'0')}</span><span>${escape(c.title)}</span></button>`).join('');
  $('chapterList').addEventListener('click', event => { const b = event.target.closest('[data-chapter]'); if(b) showChapter(book.chapters.findIndex(c => c.chapter_id === b.dataset.chapter)); });
  $('modeTabs').addEventListener('click', event => { const b = event.target.closest('[data-mode]'); if(b) changeMode(b.dataset.mode); });
  $('learningPath').addEventListener('click', event => { const b = event.target.closest('[data-step]'); if(b) changeMode(b.dataset.step); });
  $('guidedNext').addEventListener('click', () => {
    if (['meaning','spelling'].includes(mode)) { gradeAnswers(); changeMode('answers'); }
    else if (mode === 'answers') { finishedChapters.add(chapter().chapter_id); updatePath(); $('sessionEnd').scrollIntoView({block:'nearest'}); }
    else changeMode('meaning');
  });
  $('continueChapter').addEventListener('click', () => { if(chapterIndex < book.chapters.length-1) showChapter(chapterIndex+1); });
  $('recallContext').addEventListener('change', () => { rememberDraft(); recallContext = $('recallContext').value; renderContent(); });
  $('answerScope').addEventListener('change', () => { answerScope = $('answerScope').value; renderContent(); });
  $('retryNeeds').addEventListener('click', () => {
    const grade = lastGrades.get(chapter().chapter_id);
    if (!guided || !grade?.needs.size) return;
    rememberDraft();
    mode = grade.mode; recallContext = grade.context;
    retrySessions.set(chapter().chapter_id, {mode,context:recallContext,ids:new Set(grade.needs)});
    drafts.delete(draftKey());
    renderContent(); $('modeTitle').focus();
  });
  $('returnFullExercise').addEventListener('click', () => {
    rememberDraft(); retrySessions.delete(chapter().chapter_id); renderContent(); $('modeTitle').focus();
  });
  $('readingContent').addEventListener('input', event => {
    if (!guided || !event.target.matches('input[data-answer]')) return;
    const state = drafts.get(draftKey()) || {}; state.checked = false; drafts.set(draftKey(), state);
    if (lastGrades.get(chapter().chapter_id)?.key === draftKey()) lastGrades.delete(chapter().chapter_id);
    event.target.removeAttribute('aria-invalid'); $('exerciseResult').textContent = ''; rememberDraft();
  });
  $('readingContent').addEventListener('click', event => {
    const word = event.target.closest('[data-word]'), voice = event.target.closest('[data-word-audio]'), paragraph = event.target.closest('[data-paragraph-play]');
    if (word) openWord(word.dataset.word);
    if (voice && !voice.disabled) openWord(voice.dataset.wordAudio, true);
    if (paragraph && !paragraph.disabled) { const cue = audio.chapters[chapter().chapter_id].cues.find(c => c.paragraph_id === paragraph.dataset.paragraphPlay); if(cue) { player.currentTime = cue.start; playChapter(); } }
    if(event.target.id === 'checkComprehension') chapter().questions.forEach(q => {
      const selected = document.querySelector(`input[name="${q.question_id}"]:checked`);
      $(`feedback-${q.question_id}`).textContent = !selected ? '请先选择一个答案。' : `${Number(selected.value) === q.answer_index ? '回答正确。' : '再想一想。'}${q.explanation}`;
    });
  });
  $('checkAnswers').addEventListener('click', gradeAnswers);
  $('resetAnswers').addEventListener('click', () => { if(guided) { drafts.delete(draftKey()); if(lastGrades.get(chapter().chapter_id)?.key === draftKey()) lastGrades.delete(chapter().chapter_id); } renderContent(); });
  $('previousChapter').addEventListener('click', () => showChapter(chapterIndex-1));
  $('nextChapter').addEventListener('click', () => showChapter(chapterIndex+1));
  $('closeWord').addEventListener('click', () => $('wordDialog').close());
  $('wordDialog').addEventListener('close', () => wordPlayer.pause());
  $('wordPlay').addEventListener('click', playWord);
  $('chapterPlay')?.addEventListener('click', () => player.paused ? playChapter() : player.pause());
  $('audioSpeed')?.addEventListener('change', () => { player.playbackRate = Number($('audioSpeed').value); });
  $('audioSeek')?.addEventListener('input', () => { const duration = Number.isFinite(player.duration) ? player.duration : 0; if(duration) player.currentTime = Number($('audioSeek').value)/100*duration; });
  if (player) ['play','pause','timeupdate','loadedmetadata','ended'].forEach(name => player.addEventListener(name, updateAudio));
  showChapter(0);
})();
