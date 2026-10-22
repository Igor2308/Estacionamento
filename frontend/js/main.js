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

let _timer;
function aviso(texto, tipo = "ok") {
  let el = document.getElementById("aviso");
  if (!el) { el = document.createElement("div"); el.id = "aviso"; document.body.appendChild(el); }
  el.textContent = texto; el.className = tipo; el.style.display = "block";
  clearTimeout(_timer); _timer = setTimeout(() => (el.style.display = "none"), 4500);
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
