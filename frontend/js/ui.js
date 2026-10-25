/* Componentes de tela compartilhados: máscaras, formulário em sequência, busca com lista e paginação. */

const TIPOS_VEICULO = { CARRO: "Carro", MOTO: "Moto", VAN: "Van", CAMINHAO: "Caminhão", OUTRO: "Outro" };

/* ---------- formatação e validação de dados ---------- */
const soDigitos = v => String(v ?? "").replace(/\D/g, "");

function fmtCPF(v) {
  const d = soDigitos(v).slice(0, 11);
  return d.slice(0, 3) + (d.length > 3 ? "." + d.slice(3, 6) : "") + (d.length > 6 ? "." + d.slice(6, 9) : "") + (d.length > 9 ? "-" + d.slice(9, 11) : "");
}
function fmtCNPJ(v) {
  const d = soDigitos(v).slice(0, 14);
  return d.slice(0, 2) + (d.length > 2 ? "." + d.slice(2, 5) : "") + (d.length > 5 ? "." + d.slice(5, 8) : "") +
    (d.length > 8 ? "/" + d.slice(8, 12) : "") + (d.length > 12 ? "-" + d.slice(12, 14) : "");
}
function fmtTel(v) {
  const d = soDigitos(v).slice(0, 11);
  if (!d) return "";
  const meio = d.length > 10 ? 5 : 4;
  return "(" + d.slice(0, 2) + (d.length >= 2 ? ")" : "") + (d.length > 2 ? " " + d.slice(2, 2 + meio) : "") + (d.length > 2 + meio ? "-" + d.slice(2 + meio) : "");
}
function fmtCEP(v) {
  const d = soDigitos(v).slice(0, 8);
  return d.slice(0, 5) + (d.length > 5 ? "-" + d.slice(5) : "");
}
const fmtDocumento = c => (c.cpf ? fmtCPF(c.cpf) : c.cnpj ? fmtCNPJ(c.cnpj) : "—");

function digitoVerificador(base, pesos) {
  const r = base.split("").reduce((s, d, i) => s + Number(d) * pesos[i], 0) % 11;
  return r < 2 ? 0 : 11 - r;
}
function cpfValido(v) {
  const d = soDigitos(v);
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
  const d1 = digitoVerificador(d.slice(0, 9), [10, 9, 8, 7, 6, 5, 4, 3, 2]);
  const d2 = digitoVerificador(d.slice(0, 9) + d1, [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]);
  return d.slice(9) === String(d1) + String(d2);
}
function cnpjValido(v) {
  const d = soDigitos(v);
  if (d.length !== 14 || /^(\d)\1{13}$/.test(d)) return false;
  const p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const d1 = digitoVerificador(d.slice(0, 12), p1);
  const d2 = digitoVerificador(d.slice(0, 12) + d1, [6, ...p1]);
  return d.slice(12) === String(d1) + String(d2);
}
const placaValida = v => /^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$/.test(String(v));
const UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"];
const emailValido = v => v.length <= 150 && /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(v);

/* filtros: tiram do campo, enquanto a pessoa digita, o que não é permitido */
const filtros = {
  letras: v => v.replace(/[^\p{L}\s'.\-]/gu, "").replace(/\s{2,}/g, " ").slice(0, 100),
  nomePF: v => v.replace(/[^\p{L}\s'.\-]/gu, "").replace(/\s{2,}/g, " ").slice(0, 150),
  nomePJ: v => v.replace(/[^\p{L}\d\s&.,'/\-]/gu, "").replace(/\s{2,}/g, " ").slice(0, 150),
  uf: v => v.replace(/[^A-Za-z]/g, "").toUpperCase().slice(0, 2),
  numero: v => v.replace(/[^0-9A-Za-z/\-\s]/g, "").slice(0, 10),
  placa: v => v.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 7),
  codigoVaga: v => v.toUpperCase().replace(/[^A-Z0-9\-]/g, "").slice(0, 20),
  dinheiro: v => {
    let t = v.replace(/[^\d,]/g, "");
    const i = t.indexOf(",");
    if (i >= 0) t = t.slice(0, i).slice(0, 8) + "," + t.slice(i + 1).replace(/,/g, "").slice(0, 2);
    else t = t.slice(0, 8);
    return t;
  },
  texto: max => v => v.replace(/\s{2,}/g, " ").slice(0, max),
};
const numeroDinheiro = t => Number(String(t).replace(",", "."));
const dinheiroValido = t => /^\d{1,8}(,\d{1,2})?$/.test(t);

/* ---------- máscara com cursor no lugar certo ---------- */
function ligarMascara(input, formatar) {
  input.addEventListener("input", () => {
    const pos = input.selectionStart ?? input.value.length;
    const antes = soDigitos(input.value.slice(0, pos)).length;
    const fim = pos >= input.value.length;
    input.value = formatar(input.value);
    if (fim) return;
    let n = 0, novoPos = input.value.length;
    if (antes === 0) novoPos = 0;
    else for (let i = 0; i < input.value.length; i++) { if (/\d/.test(input.value[i]) && ++n === antes) { novoPos = i + 1; break; } }
    try { input.setSelectionRange(novoPos, novoPos); } catch (e) { /* tipo sem seleção */ }
  });
}

/* ---------- formulário em sequência ----------
   Só o primeiro campo começa habilitado. Cada campo só libera o seguinte quando o seu valor é válido;
   o erro aparece embaixo do próprio campo. O botão só habilita quando tudo estiver válido.

   campo = { el, nome?, filtro?, mascara?, tamanho?, opcional?, visivel?(), bloqueado?(), validar?(valor, ctx),
             assincrono?(valor) -> Promise<string|null>, valor?() , extras?: [elementos desabilitados junto],
             caixa?: elemento que esconde com o campo }                                                        */
function formularioSequencial({ campos, botao, form, aoAvaliar }) {
  const estado = new Map();
  const st = c => { if (!estado.has(c)) estado.set(c, { tocado: false, async: null }); return estado.get(c); };
  const lerValor = c => (c.valor ? c.valor() : c.el.type === "checkbox" ? (c.el.checked ? "1" : "") : String(c.el.value ?? "").trim());
  const caixaDe = c => c.caixa || c.el.closest("label") || c.el.parentElement;

  function areaErro(c) {
    const caixa = caixaDe(c);
    let el = caixa.querySelector(":scope > .erro-campo, :scope > .info-campo");
    if (!el) { el = document.createElement("small"); caixa.appendChild(el); }
    return el;
  }
  function mostrar(c, msg, info = false) {
    const a = areaErro(c);
    a.className = info ? "info-campo" : "erro-campo";
    a.textContent = msg || "";
    a.hidden = !msg;
    c.el.classList.toggle("invalido", !!msg && !info);
    c.el.setAttribute("aria-invalid", !!msg && !info ? "true" : "false");
  }
  const desabilitar = (c, v) => {
    c.el.disabled = v;
    (c.extras || []).forEach(x => (x.disabled = v));
  };

  /* devolve { ok, msg, info } do campo (sem considerar se está liberado) */
  function checar(c) {
    const v = lerValor(c);
    if (!v) return c.opcional || c.el.type === "checkbox" ? { ok: true } : { ok: false, msg: c.erroVazio || "Preencha este campo.", vazio: true };
    const msg = c.validar ? c.validar(v) : null;
    if (msg) return { ok: false, msg };
    if (c.assincrono) {
      const s = st(c);
      if (!s.async || s.async.valor !== v) {
        const marca = { valor: v, fim: false, msg: null };
        s.async = marca;
        Promise.resolve(c.assincrono(v)).then(m => { marca.msg = m || null; }, () => { marca.msg = null; })
          .finally(() => { marca.fim = true; if (st(c).async === marca) avaliar(); });
      }
      if (!s.async.fim) return { ok: false, msg: "Verificando…", info: true };
      if (s.async.msg) return { ok: false, msg: s.async.msg, forte: true };
    }
    return { ok: true };
  }

  function avaliar() {
    let liberado = true, tudoOk = true;
    campos.forEach(c => {
      const visivel = c.visivel ? c.visivel() : true;
      const caixa = caixaDe(c);
      if (caixa) caixa.classList.toggle("oculto", !visivel);
      if (!visivel) { desabilitar(c, true); mostrar(c, ""); return; }
      if (c.bloqueado && c.bloqueado()) { desabilitar(c, true); mostrar(c, ""); return; }
      desabilitar(c, !liberado);
      const r = checar(c);
      if (!liberado) mostrar(c, "");
      else if (!r.ok && (r.forte || r.info || st(c).tocado)) mostrar(c, r.msg, !!r.info);
      else mostrar(c, "");
      if (!r.ok) { liberado = false; tudoOk = false; }
    });
    if (botao) botao.disabled = !tudoOk;
    if (aoAvaliar) aoAvaliar(tudoOk);
    return tudoOk;
  }

  campos.forEach(c => {
    const el = c.el;
    const ev = el.tagName === "SELECT" || el.type === "checkbox" ? "change" : "input";
    el.addEventListener(ev, () => {
      if (c.filtro && el.type !== "checkbox" && el.tagName !== "SELECT") { const f = c.filtro(el.value); if (f !== el.value) el.value = f; }
      if (c.tamanho && soDigitos(el.value).length >= c.tamanho) st(c).tocado = true; // campo de tamanho fixo completo: já valida
      avaliar();
      if (c.aoMudar) c.aoMudar();
    });
    el.addEventListener("blur", () => { if (!el.disabled) { st(c).tocado = true; avaliar(); } });
  });
  if (form) form.addEventListener("reset", () => setTimeout(() => { limpar(); }, 0));

  function limpar() { estado.forEach(x => { x.tocado = false; x.async = null; }); avaliar(); }
  avaliar();
  return {
    avaliar, limpar,
    tocarTudo() { campos.forEach(c => (st(c).tocado = true)); return avaliar(); },
    valido: () => campos.every(c => ((c.visivel ? c.visivel() : true) && !(c.bloqueado && c.bloqueado())) ? checar(c).ok : true),
  };
}

/* ---------- caixa de busca com lista (autocompletar) ----------
   Troca "selects com milhares de itens": a pessoa digita e escolhe um item da lista que vem do servidor. */
function criarBusca(container, { placeholder = "Digite para buscar…", buscar, aoEscolher, limite = 50 }) {
  container.classList.add("combo");
  container.innerHTML = '<input type="text" class="combo-texto" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false"><ul class="combo-lista oculto" role="listbox"></ul>';
  const texto = container.querySelector(".combo-texto"), lista = container.querySelector(".combo-lista");
  texto.placeholder = placeholder;
  let itens = [], ativo = -1, escolhido = null, seq = 0, timer = null;

  const fechar = () => { lista.classList.add("oculto"); texto.setAttribute("aria-expanded", "false"); ativo = -1; };
  function desenhar(carregando = false) {
    lista.innerHTML = carregando ? '<li class="combo-vazio">Buscando…</li>'
      : itens.length ? itens.map((it, i) => `<li role="option" data-i="${i}" class="${i === ativo ? "ativo" : ""}">${esc(it.rotulo)}</li>`).join("")
        : '<li class="combo-vazio">Nada encontrado.</li>';
    lista.classList.remove("oculto"); texto.setAttribute("aria-expanded", "true");
  }
  async function consultar(t) {
    const minha = ++seq;
    desenhar(true);
    try {
      const r = (await buscar(t.trim(), limite)) || [];
      if (minha !== seq) return;
      itens = r; ativo = -1; desenhar();
    } catch (e) { if (minha === seq) { itens = []; lista.innerHTML = '<li class="combo-vazio">Não foi possível buscar agora.</li>'; } }
  }
  function escolher(i) {
    const it = itens[i]; if (!it) return;
    escolhido = it; texto.value = it.rotulo; fechar();
    texto.dispatchEvent(new Event("input", { bubbles: true }));
    if (aoEscolher) aoEscolher(it);
  }
  texto.addEventListener("input", () => {
    // digitou depois de escolher: a escolha anterior deixa de valer
    if (escolhido && texto.value !== escolhido.rotulo) { escolhido = null; if (aoEscolher) aoEscolher(null); }
    if (!escolhido && document.activeElement === texto) { clearTimeout(timer); timer = setTimeout(() => consultar(texto.value), 250); }
  });
  texto.addEventListener("focus", () => { if (!escolhido && !texto.disabled) consultar(texto.value); });
  texto.addEventListener("blur", () => setTimeout(fechar, 150));
  texto.addEventListener("keydown", e => {
    const aberta = !lista.classList.contains("oculto");
    if (e.key === "ArrowDown") { e.preventDefault(); if (!aberta) return consultar(texto.value); ativo = Math.min(itens.length - 1, ativo + 1); desenhar(); }
    else if (e.key === "ArrowUp" && aberta) { e.preventDefault(); ativo = Math.max(0, ativo - 1); desenhar(); }
    else if (e.key === "Enter" && aberta && ativo >= 0) { e.preventDefault(); escolher(ativo); }
    else if (e.key === "Escape" && aberta) { e.stopPropagation(); fechar(); }
  });
  lista.addEventListener("mousedown", e => { const li = e.target.closest("li[data-i]"); if (li) { e.preventDefault(); escolher(Number(li.dataset.i)); } });

  return {
    input: texto,
    get valor() { return escolhido ? String(escolhido.id) : ""; },
    get item() { return escolhido; },
    definir(item) { escolhido = item; texto.value = item ? item.rotulo : ""; texto.dispatchEvent(new Event("input", { bubbles: true })); },
    limpar() { escolhido = null; texto.value = ""; texto.dispatchEvent(new Event("input", { bubbles: true })); },
  };
}

/* ---------- paginação: 50 por página, cada página só é carregada quando pedida ---------- */
function criarPaginador({ barra, busca, carregar, desenhar, vazio = "Nenhum registro encontrado." }) {
  let pagina = 1, total = 0, totalPaginas = 1, texto = "", seq = 0, timer = null;
  barra.classList.add("paginacao");

  async function ir(n) {
    const minha = ++seq;
    const r = await carregar(n, texto);
    if (minha !== seq || !r) return;
    pagina = r.pagina || 1; total = r.total ?? r.dados.length; totalPaginas = r.total_paginas || 1;
    desenhar(r.dados, { vazio: texto ? "Nada encontrado para essa busca." : vazio });
    barra.innerHTML = `<button type="button" class="sec mini" data-p="${pagina - 1}" ${pagina <= 1 ? "disabled" : ""}>‹ Anterior</button>
      <span>Página <b>${pagina}</b> de <b>${totalPaginas}</b> · ${total.toLocaleString("pt-BR")} registro${total === 1 ? "" : "s"}</span>
      <button type="button" class="sec mini" data-p="${pagina + 1}" ${pagina >= totalPaginas ? "disabled" : ""}>Próxima ›</button>`;
  }
  barra.addEventListener("click", e => {
    const b = e.target.closest("button[data-p]");
    if (b && !b.disabled) ir(Number(b.dataset.p));
  });
  if (busca) busca.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => { texto = busca.value.trim(); ir(1); }, 350);
  });
  return { ir, recarregar: () => ir(pagina), get pagina() { return pagina; } };
}

/* ---------- "quem fez e quando" (colunas de registro nas tabelas) ---------- */
function celulaRegistro(nome, quando, rotulo = "") {
  if (!nome && !quando) return "—";
  return `<div class="registro">${rotulo ? `<small>${esc(rotulo)}</small>` : ""}<b>${esc(nome || "—")}</b><small>${dataHora(quando)}</small></div>`;
}
/* cadastro + (se houve) última alteração */
function celulaCadastro(x) {
  let h = celulaRegistro(x.cadastrado_por_nome, x.cadastrado_em);
  const alterado = x.atualizado_em && x.cadastrado_em && (new Date(x.atualizado_em) - new Date(x.cadastrado_em)) > 2000;
  if (alterado) h += celulaRegistro(x.atualizado_por_nome, x.atualizado_em, "Alterado por");
  return h;
}
