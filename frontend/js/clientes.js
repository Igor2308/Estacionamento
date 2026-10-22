let editando = null, selecionado = null, clientes = [], enderecosCli = [], editandoEnd = null;
const $ = id => document.getElementById(id);
const fmtDoc = c => c.cpf || c.cnpj || "—";

function ajustarRotuloDoc() { $("rotuloDoc").textContent = $("tipo").value === "FISICA" ? "CPF" : "CNPJ"; }
$("tipo").onchange = ajustarRotuloDoc;

async function carregar() {
  const r = await acao(() => api("/clientes"));
  if (!r) return;
  clientes = r.dados;
  $("lista").innerHTML = clientes.length ? clientes.map(c => `<tr>
    <td>${esc(c.nome)}</td><td>${c.tipo_pessoa === "FISICA" ? "PF" : "PJ"}</td><td>${esc(fmtDoc(c))}</td><td>${esc(c.telefone || "—")}</td>
    <td>${c.modalidade === "MENSALISTA" ? "Mensalista" : "Horista"}</td>
    <td><span class="tag ${c.ativo ? "ok" : "off"}">${c.ativo ? "Ativo" : "Inativo"}</span></td>
    <td><button class="mini sec" data-a="editar" data-id="${c.id_cliente}">Editar</button>
        <button class="mini sec" data-a="detalhe" data-id="${c.id_cliente}">Veículos / endereços</button>
        ${c.ativo ? `<button class="mini perigo" data-a="desativar" data-id="${c.id_cliente}">Desativar</button>` : ""}</td></tr>`).join("")
    : linhasVazias(7);
}

$("lista").onclick = async e => {
  const b = e.target.closest("button"); if (!b) return;
  const id = Number(b.dataset.id), c = clientes.find(x => x.id_cliente === id);
  if (b.dataset.a === "editar") {
    editando = id; $("tituloForm").textContent = "Editando: " + c.nome; $("cancelar").classList.remove("oculto");
    const f = $("form");
    f.nome.value = c.nome; f.tipo_pessoa.value = c.tipo_pessoa; f.documento.value = fmtDoc(c) === "—" ? "" : fmtDoc(c);
    f.telefone.value = c.telefone || ""; f.email.value = c.email || ""; f.modalidade.value = c.modalidade;
    modoEndereco(false); $("salvar").textContent = "Salvar alterações";
    ajustarRotuloDoc(); scrollTo({ top: 0, behavior: "smooth" });
  } else if (b.dataset.a === "desativar") {
    if (!confirm("Desativar " + c.nome + "?")) return;
    if (await acao(() => api("/clientes/" + id, { metodo: "DELETE" }), "Cliente desativado.")) carregar();
  } else if (b.dataset.a === "detalhe") abrirDetalhe(c);
};

/* No cadastro novo o endereço faz parte do formulário; ao editar, endereços são geridos no painel de detalhes. */
function modoEndereco(ativo) {
  $("blocoEndereco").classList.toggle("oculto", !ativo);
  $("blocoEndereco").querySelectorAll("input,select").forEach(c => (c.disabled = !ativo));
  $("dicaForm").classList.toggle("oculto", !ativo);
}
function cancelarEdicao() {
  editando = null; $("form").reset(); ajustarRotuloDoc(); modoEndereco(true);
  $("tituloForm").textContent = "Novo cliente"; $("salvar").textContent = "Salvar cliente"; $("cancelar").classList.add("oculto");
}
$("cancelar").onclick = cancelarEdicao;

$("form").onsubmit = async e => {
  e.preventDefault();
  const f = e.target;
  // validação dos campos obrigatórios (o servidor valida de novo)
  for (const campo of f.querySelectorAll("[required]")) {
    if (!campo.disabled && !String(campo.value).trim()) {
      campo.focus(); return aviso("Preencha o campo obrigatório: " + (campo.closest("label")?.firstChild?.textContent || campo.name).replace("*", "").trim() + ".", "erro");
    }
  }
  const d = formParaObjeto(f), doc = d.documento || null; delete d.documento;
  d.cpf = d.tipo_pessoa === "FISICA" ? doc : null;
  d.cnpj = d.tipo_pessoa === "JURIDICA" ? doc : null;
  const endereco = {};
  for (const k of Object.keys(d)) if (k.startsWith("end_")) { endereco[k.slice(4)] = d[k]; delete d[k]; }
  let r;
  if (editando) {
    r = await acao(() => api("/clientes/" + editando, { metodo: "PUT", corpo: d }), "Cliente atualizado.");
  } else {
    endereco.principal = true; d.endereco = endereco;
    r = await acao(() => api("/clientes", { metodo: "POST", corpo: d }), "Cliente e endereço cadastrados.");
  }
  if (r) { cancelarEdicao(); carregar(); }
};

/* ---------- veículos e endereços do cliente selecionado ---------- */
async function abrirDetalhe(c) {
  selecionado = c; cancelarEdicaoEnd(); $("detalhe").classList.remove("oculto");
  $("tituloDetalhe").textContent = "Detalhes de " + c.nome; await Promise.all([carregarVeiculos(), carregarEnderecos()]);
  $("detalhe").scrollIntoView({ behavior: "smooth" });
}
async function carregarVeiculos() {
  const r = await acao(() => api("/veiculos?id_cliente=" + selecionado.id_cliente)); if (!r) return;
  $("veiculos").innerHTML = r.dados.length ? r.dados.map(v => `<tr><td>${esc(v.placa)}</td><td>${esc(v.tipo_veiculo)}</td>
    <td>${esc([v.marca, v.modelo, v.cor].filter(Boolean).join(" ") || "—")}</td>
    <td><span class="tag ${v.ativo ? "ok" : "off"}">${v.ativo ? "Ativo" : "Inativo"}</span></td></tr>`).join("") : linhasVazias(4, "Sem veículos. Cadastre na tela Veículos.");
}
async function carregarEnderecos() {
  const r = await acao(() => api("/enderecos?id_cliente=" + selecionado.id_cliente)); if (!r) return;
  enderecosCli = r.dados;
  $("enderecos").innerHTML = r.dados.length ? r.dados.map(en => `<tr>
    <td>${esc(en.logradouro)}, ${esc(en.numero)}${en.complemento ? " - " + esc(en.complemento) : ""} • ${esc(en.bairro || "")} ${esc(en.cidade)}/${esc(en.estado)} ${esc(en.cep || "")}
    ${en.principal ? '<span class="tag ok">Principal</span>' : ""}</td><td>${esc(en.tipo_endereco)}</td>
    <td>${en.principal ? "" : `<button class="mini sec" data-a="principal" data-id="${en.id_endereco}">Tornar principal</button>`}
        <button class="mini sec" data-a="editar" data-id="${en.id_endereco}">Editar</button>
        <button class="mini perigo" data-a="excluir" data-id="${en.id_endereco}">Excluir</button></td></tr>`).join("") : linhasVazias(3, "Sem endereços.");
}
$("enderecos").onclick = async e => {
  const b = e.target.closest("button"); if (!b) return;
  const id = b.dataset.id;
  if (b.dataset.a === "editar") return editarEndereco(Number(id));
  const ok = b.dataset.a === "principal"
    ? await acao(() => api("/enderecos/" + id, { metodo: "PUT", corpo: { principal: true } }), "Endereço principal atualizado.")
    : confirm("Excluir este endereço?") && await acao(() => api("/enderecos/" + id, { metodo: "DELETE" }), "Endereço excluído.");
  if (ok) { if (String(editandoEnd) === String(id)) cancelarEdicaoEnd(); carregarEnderecos(); }
};

/* Editar endereço: o formulário de baixo é preenchido e passa a salvar (PUT) em vez de adicionar. */
function editarEndereco(id) {
  const en = enderecosCli.find(x => x.id_endereco === id); if (!en) return;
  const f = $("formEndereco");
  f.tipo_endereco.value = en.tipo_endereco; f.cep.value = en.cep || ""; f.logradouro.value = en.logradouro;
  f.numero.value = en.numero; f.complemento.value = en.complemento || ""; f.bairro.value = en.bairro || "";
  f.cidade.value = en.cidade; f.estado.value = en.estado; f.principal.checked = !!en.principal;
  editandoEnd = id; $("salvarEnd").textContent = "Salvar endereço"; $("cancelarEnd").classList.remove("oculto");
  f.scrollIntoView({ behavior: "smooth", block: "center" }); f.logradouro.focus();
}
function cancelarEdicaoEnd() {
  editandoEnd = null; $("formEndereco").reset();
  $("salvarEnd").textContent = "Adicionar outro endereço"; $("cancelarEnd").classList.add("oculto");
}
$("cancelarEnd").onclick = cancelarEdicaoEnd;
$("formEndereco").onsubmit = async e => {
  e.preventDefault();
  const d = formParaObjeto(e.target);
  if (editandoEnd) {
    // ao editar, só marca como principal se o campo estiver marcado (para desmarcar, escolha outro como principal)
    if (e.target.principal.checked) d.principal = true; else delete d.principal;
    if (await acao(() => api("/enderecos/" + editandoEnd, { metodo: "PUT", corpo: d }), "Endereço atualizado.")) { cancelarEdicaoEnd(); carregarEnderecos(); }
    return;
  }
  d.id_cliente = selecionado.id_cliente; d.principal = e.target.principal.checked;
  if (await acao(() => api("/enderecos", { metodo: "POST", corpo: d }), "Endereço cadastrado.")) { e.target.reset(); carregarEnderecos(); }
};

(async () => { await iniciarPagina("clientes"); ajustarRotuloDoc(); carregar(); })();
