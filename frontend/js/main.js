/* Utilidades compartilhadas por todas as telas */
async function api(caminho, { metodo = "GET", corpo } = {}) {
  const resp = await fetch("/api" + caminho, {
    method: metodo,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
  });
  let dados = {};
  try { dados = await resp.json(); } catch (e) { /* resposta sem corpo */ }
  if (resp.status === 401 && !location.pathname.endsWith("login.html")) {
    sessionStorage.removeItem("sessao_ativa");
    location.replace("login.html");
    throw new Error("Sessão expirada.");
  }
  if (!resp.ok) throw new Error(dados.erro || "Erro inesperado (" + resp.status + ").");
  return dados;
}

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function moeda(v) { return Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }); }
function dataHora(s) {
  if (!s) return "—";
  // o servidor devolve DATETIME sem fuso (marcado como GMT): exibimos em UTC para não deslocar o horário
  return new Date(s).toLocaleString("pt-BR", { timeZone: "UTC", dateStyle: "short", timeStyle: "short" });
}
function dataSimples(s) { return s ? new Date(s).toLocaleDateString("pt-BR", { timeZone: "UTC" }) : "—"; }

/* ---------- Modais (substituem alert / confirm / prompt e os avisos na tela) ---------- */
let _filaModais = Promise.resolve();

/* Abre um modal e devolve uma Promise com o `valor` do botão clicado (ou `cancelar` ao fechar com Esc / clique fora).
   corpo: texto (vira texto puro) ou elemento · botoes: [{ texto, valor, tipo: "primario"|"perigo"|"sec" }]
   antesDeFechar(valor, api): devolva false (ou uma Promise de false) para manter o modal aberto. */
function abrirModal({ titulo = "", corpo = "", botoes, cancelar = null, tipo = "", aoAbrir, antesDeFechar, fecharAuto = 0, focoInicial } = {}) {
  const executar = () => new Promise(resolve => {
    const anterior = document.activeElement;
    const fundo = document.createElement("div");
    fundo.className = "modal-fundo";
    const caixa = document.createElement("div");
    caixa.className = "modal " + tipo;
    caixa.setAttribute("role", "dialog");
    caixa.setAttribute("aria-modal", "true");
    const h = document.createElement("h3");
    h.textContent = titulo;
    h.id = "modalTitulo" + Date.now();
    caixa.setAttribute("aria-labelledby", h.id);
    const area = document.createElement("div");
    area.className = "modal-corpo";
    if (corpo instanceof Node) area.appendChild(corpo); else area.textContent = corpo;
    const acoes = document.createElement("div");
    acoes.className = "modal-acoes";
    const lista = botoes && botoes.length ? botoes : [{ texto: "OK", valor: true, tipo: "primario" }];
    const els = lista.map(b => {
      const el = document.createElement("button");
      el.type = "button";
      el.textContent = b.texto;
      el.className = b.tipo === "sec" ? "sec" : b.tipo === "perigo" ? "perigo" : "";
      el.dataset.principal = b.tipo === "sec" ? "" : "1";
      acoes.appendChild(el);
      return el;
    });
    if (titulo) caixa.append(h);
    caixa.append(area, acoes);
    fundo.appendChild(caixa);
    document.body.appendChild(fundo);
    document.body.classList.add("modal-aberto");

    let encerrado = false, temporizador = null;
    const api = { caixa, corpo: area, botoes: els, fechar: v => encerrar(v) };
    async function encerrar(valor) {
      if (encerrado) return;
      if (antesDeFechar && (await antesDeFechar(valor, api)) === false) return;
      encerrado = true;
      clearTimeout(temporizador);
      document.removeEventListener("keydown", teclas, true);
      fundo.remove();
      if (!document.querySelector(".modal-fundo")) document.body.classList.remove("modal-aberto");
      if (anterior && anterior.focus) try { anterior.focus(); } catch (e) { /* elemento removido */ }
      resolve(valor);
    }
    function teclas(e) {
      if (e.key === "Escape") { e.stopPropagation(); e.preventDefault(); encerrar(cancelar); return; }
      if (e.key === "Tab") {
        const foco = [...caixa.querySelectorAll("button, input, select, textarea, [tabindex]:not([tabindex='-1'])")].filter(x => !x.disabled && x.offsetParent !== null);
        if (!foco.length) return;
        const primeiro = foco[0], ultimo = foco[foco.length - 1];
        if (e.shiftKey && document.activeElement === primeiro) { e.preventDefault(); ultimo.focus(); }
        else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus(); }
        else if (!caixa.contains(document.activeElement)) { e.preventDefault(); primeiro.focus(); }
      }
    }
    document.addEventListener("keydown", teclas, true);
    els.forEach((el, i) => (el.onclick = () => encerrar(lista[i].valor)));
    fundo.addEventListener("mousedown", e => { if (e.target === fundo) encerrar(cancelar); });
    if (aoAbrir) aoAbrir(api);
    const foco = caixa.querySelector("input:not([type=hidden]), select, textarea") ||
      els[focoInicial ?? els.length - 1];
    (foco || caixa).focus();
    if (fecharAuto) temporizador = setTimeout(() => encerrar(lista[0].valor), fecharAuto);
  });
  const p = _filaModais.then(executar);
  _filaModais = p.catch(() => {});
  return p;
}

/* Mensagem na tela (erro, aviso ou sucesso). Sucesso fecha sozinho em alguns segundos; erro espera o OK. */
function aviso(texto, tipo = "ok") {
  const erro = tipo === "erro", atencao = tipo === "atencao";
  return abrirModal({
    titulo: erro ? "Atenção" : atencao ? "Aviso" : "Tudo certo",
    corpo: String(texto ?? ""),
    tipo: erro ? "erro" : atencao ? "aviso" : "ok",
    botoes: [{ texto: "OK", valor: true, tipo: "primario" }],
    cancelar: true,
    fecharAuto: erro || atencao ? 0 : 3500,
  });
}

/* Pergunta de confirmação: devolve true / false. */
function confirmar(texto, { titulo = "Confirmar", confirmar: rotulo = "Confirmar", cancelar: rotuloCancelar = "Cancelar", perigo = false } = {}) {
  return abrirModal({
    titulo, corpo: texto, tipo: perigo ? "erro" : "",
    botoes: [{ texto: rotuloCancelar, valor: false, tipo: "sec" }, { texto: rotulo, valor: true, tipo: perigo ? "perigo" : "primario" }],
    cancelar: false,
    focoInicial: perigo ? 0 : undefined, // ação destrutiva: o foco começa em "Cancelar"
  });
}

/* Pede um texto: devolve o texto digitado ou null. `validar(texto)` devolve a mensagem de erro (ou null). */
function perguntar(texto, { titulo = "Informe", valorInicial = "", maxlength = 100, validar, confirmar: rotulo = "Salvar" } = {}) {
  const corpo = document.createElement("div");
  const p = document.createElement("p"); p.textContent = texto; p.style.margin = "0 0 .6rem";
  const input = document.createElement("input");
  input.type = "text"; input.maxLength = maxlength; input.value = valorInicial; input.style.width = "100%";
  const erro = document.createElement("small"); erro.className = "erro-campo";
  corpo.append(p, input, erro);
  input.addEventListener("input", () => (erro.textContent = ""));
  input.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); corpo.closest(".modal").querySelector(".modal-acoes button[data-principal='1']").click(); } });
  return abrirModal({
    titulo, corpo,
    botoes: [{ texto: "Cancelar", valor: null, tipo: "sec" }, { texto: rotulo, valor: "ok", tipo: "primario" }],
    cancelar: null,
    antesDeFechar: v => {
      if (v !== "ok") return true;
      const t = input.value.trim().replace(/\s+/g, " ");
      const msg = !t ? "Preencha este campo." : validar ? validar(t) : null;
      if (msg) { erro.textContent = msg; input.focus(); return false; }
      return true;
    },
  }).then(v => (v === "ok" ? input.value.trim().replace(/\s+/g, " ") : null));
}

async function acao(fn, sucesso) {
  try { const r = await fn(); if (sucesso) aviso(typeof sucesso === "function" ? sucesso(r) : sucesso); return r; }
  catch (e) { aviso(e.message, "erro"); return null; }
}

function formParaObjeto(form) {
  const o = {};
  new FormData(form).forEach((v, k) => { o[k] = typeof v === "string" ? v.trim() : v; });
  return o;
}
function linhasVazias(cols, texto = "Nada cadastrado ainda.") {
  return `<tr><td colspan="${cols}" class="vazio">${texto}</td></tr>`;
}

const PAGINAS = [["dashboard", "Painel"], ["clientes", "Clientes"], ["veiculos", "Veículos"], ["vagas", "Vagas"], ["movimentacoes", "Entradas e saídas"], ["pagamentos", "Pagamentos"], ["tarifas", "Tarifas"]];

/* Autenticação no navegador:
   - o servidor só entrega as telas e a API a quem tem sessão (cookie);
   - a "sessao_ativa" fica na ABA (sessionStorage): ao fechar a aba ou abrir o endereço numa aba nova,
     ela não existe e o login é pedido de novo. */
async function sair() {
  try { await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }); } catch (e) { /* segue para o login */ }
  sessionStorage.removeItem("sessao_ativa");
  location.replace("login.html");
  return new Promise(() => {}); // não deixa o restante da tela carregar
}

// Voltar/avançar pelo navegador pode mostrar a tela guardada em memória: recarrega para o servidor conferir a sessão.
if (!location.pathname.endsWith("login.html")) {
  addEventListener("pageshow", e => { if (e.persisted) location.reload(); });
}

async function iniciarPagina(atual) {
  if (!sessionStorage.getItem("sessao_ativa")) return sair();
  const cab = document.createElement("header");
  cab.innerHTML = `<strong>🅿️ Estacionamento</strong><nav>${PAGINAS.map(([p, t]) =>
    `<a href="${p}.html" class="${p === atual ? "ativo" : ""}">${t}</a>`).join("")}</nav>
    <span class="usuario" id="usuario"></span><button class="sec mini" id="sair">Sair</button>`;
  document.body.prepend(cab);
  document.getElementById("sair").onclick = sair;
  const s = await api("/auth/sessao"); // sem sessão válida, api() leva ao login
  document.getElementById("usuario").textContent = s.usuario.nome;
  document.documentElement.classList.add("ok"); // só agora a tela aparece
}
