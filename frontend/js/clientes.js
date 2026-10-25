const $ = id => document.getElementById(id);
const enc = encodeURIComponent;
let editando = null, enderecosCli = [], editandoEnd = null, paginador;

/* ---------- campos de endereço (os mesmos no cadastro novo e na edição) ---------- */
function htmlCamposEndereco(p, { principal = false } = {}) {
  return `
<label>Tipo *<select id="${p}_tipo"><option value="RESIDENCIAL">Residencial</option><option value="COMERCIAL">Comercial</option><option value="COBRANCA">Cobrança</option><option value="OUTRO">Outro</option></select></label>
<label>País *<input id="${p}_pais" value="Brasil" placeholder="País"></label>
<label>CEP *<input id="${p}_cep" inputmode="numeric" placeholder="00000-000"></label>
<label class="largo">Logradouro *<input id="${p}_logradouro" placeholder="Rua, avenida…"></label>
<label>Nº *<input id="${p}_numero" size="6" placeholder="123"></label>
<label>Complemento <span class="rotulo-opcional">(opcional)</span><input id="${p}_complemento"></label>
<label>Bairro *<input id="${p}_bairro"></label>
<label>Cidade *<input id="${p}_cidade"></label>
<label>UF *<input id="${p}_estado" size="3" placeholder="SP" style="text-transform:uppercase"></label>
${principal ? `<label class="check"><input type="checkbox" id="${p}_principal"> Endereço principal</label>` : ""}`;
}

const cacheCep = new Map();   // CEP (8 dígitos) -> resposta do ViaCEP
const cepJaPreenchido = {};   // prefixo -> CEP que veio de um endereço salvo (não consulta de novo)

/* Constrói a lista de campos (em ordem) de um endereço; `visivel` e `principal` opcionais. */
function camposEndereco(p, { visivel, principal = false } = {}) {
  const el = s => $(`${p}_${s}`);
  const brasil = () => /^\s*(brasil|brazil)\s*$/i.test(el("pais").value);
  const vis = visivel ? { visivel } : {};

  ligarMascara(el("cep"), v => (brasil() ? fmtCEP(v) : v));

  async function consultarCep(cepDigitado) {
    if (!brasil()) return null;
    const d = soDigitos(cepDigitado);
    if (cepJaPreenchido[p] === d) return null;
    aviso_(null);
    let j = cacheCep.get(d);
    if (!j) {
      try {
        const ctl = new AbortController();
        const t = setTimeout(() => ctl.abort(), 7000);
        const r = await fetch(`https://viacep.com.br/ws/${d}/json/`, { signal: ctl.signal });
        clearTimeout(t);
        if (!r.ok) throw new Error("ViaCEP indisponível");
        j = await r.json();
        cacheCep.set(d, j);
      } catch (e) {
        aviso_("Não foi possível consultar o CEP agora. Preencha o endereço manualmente.");
        return null; // sem internet/ViaCEP fora do ar: o cadastro continua manual
      }
    }
    if (j.erro) return "CEP não encontrado. Confira os números.";
    if (soDigitos(el("cep").value) !== d) return null; // a pessoa já mudou o CEP enquanto consultava
    el("logradouro").value = (j.logradouro || "").slice(0, 150);
    el("bairro").value = (j.bairro || "").slice(0, 100);
    el("cidade").value = filtros.letras(j.localidade || "");
    el("estado").value = (j.uf || "").toUpperCase();
    setTimeout(() => { const prox = ["logradouro", "numero", "bairro", "cidade", "estado"].map(el).find(x => !x.value); if (prox && !prox.disabled) prox.focus(); }, 40);
    return null;
  }
  function aviso_(msg) {
    let a = el("cep").parentElement.querySelector(".aviso-campo");
    if (!a) { a = document.createElement("small"); a.className = "aviso-campo"; el("cep").parentElement.appendChild(a); }
    a.textContent = msg || ""; a.hidden = !msg;
  }
  el("cep").addEventListener("input", () => aviso_(null));

  const campos = [
    { el: el("tipo"), ...vis },
    { el: el("pais"), filtro: filtros.letras, ...vis,
      validar: v => (v.replace(/[^\p{L}]/gu, "").length < 2 ? "País inválido. Use somente letras." : null) },
    { el: el("cep"), ...vis, tamanho: 8,
      filtro: v => (brasil() ? fmtCEP(v) : v.replace(/[^0-9A-Za-z\- ]/g, "").toUpperCase().slice(0, 9)),
      validar: v => brasil()
        ? (soDigitos(v).length !== 8 ? "CEP incompleto: informe os 8 números." : null)
        : (v.length < 3 ? "Código postal muito curto." : null),
      assincrono: consultarCep },
    { el: el("logradouro"), filtro: filtros.texto(150), ...vis, validar: v => (v.length < 3 ? "Informe o logradouro (mínimo 3 caracteres)." : null) },
    { el: el("numero"), filtro: filtros.numero, ...vis, validar: v => (/[0-9A-Za-z]/.test(v) ? null : "Informe o número (ou S/N).") },
    { el: el("complemento"), filtro: filtros.texto(100), opcional: true, ...vis },
    { el: el("bairro"), filtro: filtros.texto(100), ...vis, validar: v => (v.length < 2 ? "Informe o bairro." : null) },
    { el: el("cidade"), filtro: filtros.letras, ...vis, validar: v => (v.replace(/[^\p{L}]/gu, "").length < 2 ? "Cidade inválida. Use somente letras." : null) },
    { el: el("estado"), filtro: filtros.uf, ...vis, tamanho: 2,
      validar: v => (v.length !== 2 ? "Informe a sigla do estado com 2 letras."
        : brasil() && !UFS.includes(v.toUpperCase()) ? "UF inválida. Use a sigla de um estado brasileiro (ex.: SP)." : null) },
  ];
  if (principal) campos.push({ el: el("principal"), opcional: true, ...vis });
  const ler = () => ({
    tipo_endereco: el("tipo").value, pais: el("pais").value.trim(), cep: el("cep").value.trim(),
    logradouro: el("logradouro").value.trim(), numero: el("numero").value.trim(),
    complemento: el("complemento").value.trim(), bairro: el("bairro").value.trim(),
    cidade: el("cidade").value.trim(), estado: el("estado").value.trim().toUpperCase(),
  });
  return { campos, ler, el, brasil };
}

/* ---------- formulário do cliente ---------- */
$("camposEnderecoNovo").innerHTML = htmlCamposEndereco("en");
$("camposEnderecoEdicao").innerHTML = htmlCamposEndereco("ae", { principal: true });

const ehPF = () => $("tipo").value === "FISICA";
const maskDoc = v => (ehPF() ? fmtCPF(v) : fmtCNPJ(v));
ligarMascara($("documento"), maskDoc);
ligarMascara($("telefone"), fmtTel);

const valorBusca = combo => combo.valor || (combo.input.value.trim() ? "?" : "");
const MAX_VAGAS = 10;
const mensalista = () => $("modalidade").value === "MENSALISTA" && !editando;
const qtdVagas = () => Number($("qtdVagas").value) || 1;

/* Uma caixa de busca por vaga contratada. Cada uma esconde as vagas já escolhidas nas outras. */
$("linhaVagas").innerHTML = Array.from({ length: MAX_VAGAS }, (_, i) =>
  `<label id="caixaVaga${i}">Vaga ${i + 1} *<div id="comboVaga${i}"></div></label>`).join("");
const combosVaga = Array.from({ length: MAX_VAGAS }, (_, i) => criarBusca($(`comboVaga${i}`), {
  placeholder: "Digite o código da vaga…",
  buscar: async texto => {
    const usadas = combosVaga.filter((c, j) => j !== i && c.valor).map(c => Number(c.valor));
    return (await api(`/vagas?livres=1&pagina=1&busca=${enc(texto)}`)).dados
      .filter(v => !usadas.includes(v.id_vaga))
      .map(v => ({ id: v.id_vaga, rotulo: `${v.codigo} — ${TIPOS_VEICULO[v.tipo_veiculo] || v.tipo_veiculo}${v.setor ? " • " + v.setor : ""}` }));
  },
}));
const limparVagas = (desde = 0) => combosVaga.forEach((c, i) => { if (i >= desde) c.limpar(); });

const endNovo = camposEndereco("en", { visivel: () => !editando });

const seqCliente = formularioSequencial({
  form: $("form"), botao: $("salvar"),
  aoAvaliar: () => $("linhaVagas").classList.toggle("oculto", !mensalista()),
  campos: [
    { el: $("nome"), tamanho: 0, filtro: v => (ehPF() ? filtros.nomePF(v) : filtros.nomePJ(v)),
      validar: v => (ehPF()
        ? (v.replace(/[^\p{L}]/gu, "").length < 3 ? "Informe o nome (mínimo 3 letras, sem números)." : null)
        : (v.length < 3 ? "Informe o nome da empresa (mínimo 3 caracteres)." : null)) },
    { el: $("tipo"), bloqueado: () => !!editando,
      aoMudar: () => {
        $("documento").value = "";
        $("rotuloDoc").textContent = ehPF() ? "CPF" : "CNPJ";
        $("documento").placeholder = ehPF() ? "000.000.000-00" : "00.000.000/0000-00";
        $("nome").value = (ehPF() ? filtros.nomePF : filtros.nomePJ)($("nome").value);
        seqCliente.limpar();
      } },
    { el: $("documento"), bloqueado: () => !!editando, filtro: maskDoc, tamanho: 11,
      validar: v => {
        const n = soDigitos(v).length, rot = ehPF() ? "CPF" : "CNPJ", tam = ehPF() ? 11 : 14;
        if (n < tam) return `${rot} incompleto: informe os ${tam} números.`;
        return (ehPF() ? cpfValido(v) : cnpjValido(v)) ? null : `${rot} inválido. Confira os números.`;
      },
      assincrono: async v => {
        const d = soDigitos(v);
        try {
          const r = await api(`/clientes?pagina=1&busca=${d}`);
          const igual = r.dados.find(c => (c.cpf || c.cnpj) === d);
          return igual ? `Já existe um cliente com este ${ehPF() ? "CPF" : "CNPJ"}: ${igual.nome}.` : null;
        } catch (e) { return null; } // o servidor confere de novo ao salvar
      } },
    { el: $("telefone"), filtro: fmtTel, tamanho: 10,
      validar: v => {
        const d = soDigitos(v);
        if (d.length < 10) return "Telefone incompleto: informe o DDD e o número.";
        if (d.slice(0, 2) < "11") return "DDD inválido.";
        if (d.length === 11 && d[2] !== "9") return "Celular deve começar com 9 depois do DDD.";
        return null;
      } },
    { el: $("email"), opcional: true, filtro: v => v.replace(/\s/g, "").slice(0, 150),
      validar: v => (emailValido(v) ? null : "E-mail inválido (exemplo: nome@dominio.com).") },
    { el: $("modalidade"),
      aoMudar: () => { if ($("modalidade").value !== "MENSALISTA") limparVagas(); seqCliente.avaliar(); } },
    { el: $("qtdVagas"), caixa: $("caixaQtd"), visivel: mensalista,
      aoMudar: () => { limparVagas(qtdVagas()); seqCliente.avaliar(); } },
    ...combosVaga.map((combo, i) => ({
      el: combo.input, caixa: $(`caixaVaga${i}`), valor: () => valorBusca(combo),
      visivel: () => mensalista() && i < qtdVagas(),
      erroVazio: `Escolha a vaga ${i + 1}.`,
      validar: v => (v === "?" ? "Escolha uma vaga da lista." : null),
    })),
    ...endNovo.campos,
  ],
});

function limparFormulario() {
  editando = null;
  $("form").reset(); limparVagas();
  $("rotuloDoc").textContent = "CPF"; $("documento").placeholder = "000.000.000-00";
  $("tituloForm").textContent = "Novo cliente"; $("salvar").textContent = "Salvar cliente";
  $("cancelar").classList.add("oculto"); $("painelEnderecos").classList.add("oculto");
  $("blocoEndereco").classList.remove("oculto"); $("dicaForm").classList.remove("oculto");
  cancelarEdicaoEnd();
  seqCliente.limpar();
}
$("cancelar").onclick = limparFormulario;

$("form").onsubmit = async e => {
  e.preventDefault();
  if (!seqCliente.tocarTudo()) return;
  const d = {
    nome: $("nome").value.trim().replace(/\s+/g, " "), telefone: soDigitos($("telefone").value),
    email: $("email").value.trim(), modalidade: $("modalidade").value,
  };
  let r;
  if (editando) {
    r = await acao(() => api("/clientes/" + editando, { metodo: "PUT", corpo: d }), "Cliente atualizado.");
  } else {
    const doc = soDigitos($("documento").value);
    d.tipo_pessoa = $("tipo").value;
    d.cpf = ehPF() ? doc : null; d.cnpj = ehPF() ? null : doc;
    d.endereco = { ...endNovo.ler(), principal: true };
    if (d.modalidade === "MENSALISTA") d.id_vagas = combosVaga.slice(0, qtdVagas()).map(c => Number(c.valor));
    r = await acao(() => api("/clientes", { metodo: "POST", corpo: d }), x => x.mensagem);
  }
  if (r) { limparFormulario(); paginador.recarregar(); }
};

/* ---------- lista (50 por página, busca por nome ou CPF/CNPJ) ---------- */
let clientes = [];
paginador = criarPaginador({
  barra: $("paginacao"), busca: $("busca"),
  carregar: (pagina, texto) => acao(() => api(`/clientes?pagina=${pagina}&busca=${enc(texto)}`)),
  desenhar: (dados, { vazio }) => {
    clientes = dados;
    $("lista").innerHTML = dados.length ? dados.map(c => `<tr>
      <td>${esc(c.nome)}</td><td>${c.tipo_pessoa === "FISICA" ? "PF" : "PJ"}</td><td>${esc(fmtDocumento(c))}</td><td>${esc(c.telefone ? fmtTel(c.telefone) : "—")}</td>
      <td>${c.modalidade === "MENSALISTA" ? "Mensalista" : "Horista"}</td>
      <td><span class="tag ${c.ativo ? "ok" : "off"}">${c.ativo ? "Ativo" : "Inativo"}</span></td>
      <td><button class="mini sec" data-a="editar" data-id="${c.id_cliente}">Editar</button>
          ${c.ativo ? `<button class="mini perigo" data-a="desativar" data-id="${c.id_cliente}">Desativar</button>` : ""}</td></tr>`).join("")
      : linhasVazias(7, vazio);
  },
});

$("lista").onclick = async e => {
  const b = e.target.closest("button"); if (!b) return;
  const id = Number(b.dataset.id), c = clientes.find(x => x.id_cliente === id);
  if (!c) return;
  if (b.dataset.a === "editar") iniciarEdicao(c);
  else if (b.dataset.a === "desativar") {
    if (!(await confirmar(`Desativar o cliente ${c.nome}?`, { titulo: "Desativar cliente", confirmar: "Desativar", perigo: true }))) return;
    if (await acao(() => api("/clientes/" + id, { metodo: "DELETE" }), "Cliente desativado.")) {
      if (editando === id) limparFormulario();
      paginador.recarregar();
    }
  }
};

/* ---------- edição: dados + endereços, tudo no topo ---------- */
function iniciarEdicao(c) {
  limparFormulario();
  editando = c.id_cliente;
  $("tituloForm").textContent = "Editando: " + c.nome;
  $("salvar").textContent = "Salvar alterações";
  $("cancelar").classList.remove("oculto");
  $("blocoEndereco").classList.add("oculto"); $("dicaForm").classList.add("oculto");
  $("nome").value = c.nome; $("tipo").value = c.tipo_pessoa;
  $("rotuloDoc").textContent = ehPF() ? "CPF" : "CNPJ";
  $("documento").value = maskDoc(c.cpf || c.cnpj || "");
  $("telefone").value = fmtTel(c.telefone || ""); $("email").value = c.email || "";
  $("modalidade").value = c.modalidade;
  $("painelEnderecos").classList.remove("oculto");
  seqCliente.limpar();
  carregarEnderecos();
  scrollTo({ top: 0, behavior: "smooth" });
}

const endEdicao = camposEndereco("ae", { principal: true });
const seqEnd = formularioSequencial({ form: $("formEndereco"), botao: $("salvarEnd"), campos: endEdicao.campos });

async function carregarEnderecos() {
  const r = await acao(() => api("/enderecos?id_cliente=" + editando)); if (!r) return;
  enderecosCli = r.dados;
  $("enderecos").innerHTML = r.dados.length ? r.dados.map(en => `<tr>
    <td>${esc(en.logradouro)}, ${esc(en.numero)}${en.complemento ? " - " + esc(en.complemento) : ""} • ${esc(en.bairro || "")} ${esc(en.cidade)}/${esc(en.estado)} ${esc(en.cep || "")}${en.pais && !/^brasil$/i.test(en.pais) ? " • " + esc(en.pais) : ""}
    ${en.principal ? '<span class="tag ok">Principal</span>' : ""}</td><td>${esc(en.tipo_endereco)}</td>
    <td>${en.principal ? "" : `<button class="mini sec" data-a="principal" data-id="${en.id_endereco}">Tornar principal</button>`}
        <button class="mini sec" data-a="editar" data-id="${en.id_endereco}">Editar</button>
        <button class="mini perigo" data-a="excluir" data-id="${en.id_endereco}">Excluir</button></td></tr>`).join("") : linhasVazias(3, "Sem endereços.");
}
$("enderecos").onclick = async e => {
  const b = e.target.closest("button"); if (!b) return;
  const id = Number(b.dataset.id);
  if (b.dataset.a === "editar") return editarEndereco(id);
  let ok;
  if (b.dataset.a === "principal") {
    ok = await acao(() => api("/enderecos/" + id, { metodo: "PUT", corpo: { principal: true } }), "Endereço principal atualizado.");
  } else {
    if (enderecosCli.length <= 1) return aviso("O cliente precisa ter pelo menos um endereço. Cadastre outro antes de excluir este.", "erro");
    if (!(await confirmar("Excluir este endereço?", { titulo: "Excluir endereço", confirmar: "Excluir", perigo: true }))) return;
    ok = await acao(() => api("/enderecos/" + id, { metodo: "DELETE" }), "Endereço excluído.");
  }
  if (ok) { if (editandoEnd === id) cancelarEdicaoEnd(); carregarEnderecos(); }
};

/* Editar endereço: o formulário logo abaixo da lista (no topo da tela) é preenchido; nada de rolar a página. */
function editarEndereco(id) {
  const en = enderecosCli.find(x => x.id_endereco === id); if (!en) return;
  const el = endEdicao.el;
  cepJaPreenchido.ae = soDigitos(en.cep || "");
  el("tipo").value = en.tipo_endereco; el("pais").value = en.pais || "Brasil"; el("cep").value = en.cep || "";
  el("logradouro").value = en.logradouro; el("numero").value = en.numero; el("complemento").value = en.complemento || "";
  el("bairro").value = en.bairro || ""; el("cidade").value = en.cidade; el("estado").value = en.estado;
  el("principal").checked = !!en.principal;
  editandoEnd = id;
  $("tituloEnd").textContent = "Editando endereço"; $("salvarEnd").textContent = "Salvar endereço";
  $("cancelarEnd").classList.remove("oculto");
  seqEnd.limpar();
  setTimeout(() => el("logradouro").focus(), 60); // depois que a sequência liberar os campos
}
function cancelarEdicaoEnd() {
  editandoEnd = null; cepJaPreenchido.ae = null;
  $("formEndereco").reset();
  $("tituloEnd").textContent = "Adicionar endereço"; $("salvarEnd").textContent = "Adicionar endereço";
  $("cancelarEnd").classList.add("oculto");
  seqEnd.limpar();
}
$("cancelarEnd").onclick = cancelarEdicaoEnd;

$("formEndereco").onsubmit = async e => {
  e.preventDefault();
  if (!seqEnd.tocarTudo()) return;
  const d = endEdicao.ler(), principal = endEdicao.el("principal").checked;
  if (editandoEnd) {
    // ao editar, só marca como principal se o campo estiver marcado (para trocar, escolha outro como principal)
    if (principal) d.principal = true;
    if (await acao(() => api("/enderecos/" + editandoEnd, { metodo: "PUT", corpo: d }), "Endereço atualizado.")) { cancelarEdicaoEnd(); carregarEnderecos(); }
    return;
  }
  d.id_cliente = editando; d.principal = principal;
  if (await acao(() => api("/enderecos", { metodo: "POST", corpo: d }), "Endereço cadastrado.")) { cancelarEdicaoEnd(); carregarEnderecos(); }
};

(async () => {
  await iniciarPagina("clientes"); paginador.ir(1);
  if (new URLSearchParams(location.search).has("novo")) $("nome").focus(); // vindo do botão "Novo cliente" do painel
})();
